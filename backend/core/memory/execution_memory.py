"""
core/memory/execution_memory.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Redis-backed execution memory for the LangNeurons freeze phase.

Key schema:
    execution_history:{session_id}:{agent_name}
    → JSON list of AgentTurnRecord objects (append-only, never deleted)

Each agent reads its own history before making routing decisions.
History is appended at the end of every human turn.

Includes "Superconscious Memory": Auto-compresses every 10 turns to prevent context window explosion.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from ..engine.memory import RedisClient

_redis_instance = RedisClient()
_redis = _redis_instance.get_client()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _redis_key(session_id: str, agent_name: str) -> str:
    return f"execution_history:{session_id}:{agent_name}"


# ─────────────────────────────────────────────────────────────────────────────
# DECAYING MEMORY COMPRESSION (Short-Term -> Medium-Term -> Long-Term)
# ─────────────────────────────────────────────────────────────────────────────

def get_memory_thresholds() -> tuple[int, int, int]:
    """
    Returns (raw_threshold, medium_threshold, batch_size) dynamically.
    Reads from environment variables if set.
    Otherwise, auto-scales based on the active LLM_PROVIDER in the system.
    """
    import os
    
    # 1. Check if user explicitly defined them in env
    raw_env = os.getenv("MEMORY_RAW_THRESHOLD")
    med_env = os.getenv("MEMORY_MEDIUM_THRESHOLD")
    batch_env = os.getenv("MEMORY_DECAY_BATCH_SIZE")
    
    # 2. Get LLM provider to compute smart defaults
    provider = os.getenv("LLM_PROVIDER", "moonshot").lower()
    
    # Smart defaults based on LLM context windows:
    if provider in ("gemini", "google"):
        # Gemini has a massive context window (up to 2M tokens).
        default_raw = 30
        default_med = 60
        default_batch = 15
    elif provider in ("moonshot", "kimi"):
        # Kimi-k2.5 has 128k context, perfect for 20 turns.
        default_raw = 20
        default_med = 40
        default_batch = 10
    elif provider == "openai":
        # GPT-4o-mini is efficient but we keep it tight (15 turns) to save tokens.
        default_raw = 15
        default_med = 30
        default_batch = 8
    else:
        # Default fallback
        default_raw = 20
        default_med = 40
        default_batch = 10
        
    raw = int(raw_env) if raw_env else default_raw
    med = int(med_env) if med_env else default_med
    batch = int(batch_env) if batch_env else default_batch
    
    return raw, med, batch


def _compress_history(agent_name: str, existing_history: list) -> list:
    """
    Implements a 3-tier Decaying Memory architecture:
    1. Short-Term (Raw): Last N turns are kept uncompressed.
    2. Medium-Term (50% compression): Once uncompressed hits raw_threshold, oldest batch moves here.
    3. Long-Term (10% compression): Once Medium-Term hits medium_threshold turns, it flushes here.
    
    All thresholds are configurable via env variables or auto-scaled by the active LLM provider.
    """
    raw_threshold, medium_threshold, batch_size = get_memory_thresholds()
    
    long_term = next((t for t in existing_history if t.get("memory_tier") == "long_term"), None)
    medium_term = next((t for t in existing_history if t.get("memory_tier") == "medium_term"), None)
    
    # Filter out compressed blocks to get raw short-term turns
    # (also handle backwards compatibility with 'compressed_summary')
    uncompressed = [t for t in existing_history if "memory_tier" not in t and "compressed_summary" not in t]
    
    # For backwards compatibility with the old 50% flat compression:
    # If a legacy 'compressed_summary' exists, treat it as the medium_term
    if not medium_term:
        legacy = next((t for t in existing_history if "compressed_summary" in t), None)
        if legacy:
            medium_term = {
                "memory_tier": "medium_term",
                "summary": legacy["compressed_summary"],
                "turns_covered": legacy.get("turns_covered", 10)
            }
            
    updated = False
    
    # We only import LLM if a compression is needed
    if (medium_term and medium_term.get("turns_covered", 0) >= medium_threshold) or len(uncompressed) >= raw_threshold:
        from ..llm.connector import LLMConnector
        from langchain_core.messages import SystemMessage, HumanMessage
        llm = LLMConnector.get_llm(purpose="execution")

        # 1. Medium-Term -> Long-Term Decay
        if medium_term and medium_term.get("turns_covered", 0) >= medium_threshold:
            print(f"🗜️  [Memory] Decaying: Moving Medium-Term to Long-Term for {agent_name}...")
            lt_text = long_term["summary"] if long_term else "None."
            mt_text = medium_term["summary"]
            
            sys_msg = SystemMessage(content=(
                f"You are the memory subsystem for the AI agent '{agent_name}'.\n"
                "Merge the existing LONG-TERM memory with the decaying MEDIUM-TERM memory into a single LONG-TERM summary.\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. Compress down to ~10% size. This is LONG-TERM memory.\n"
                "2. Keep only the ultimate outcomes, major architectural decisions, and final states.\n"
                "3. Drop specific file names unless critical. Drop all minor debugging steps."
            ))
            user_msg = HumanMessage(content=f"[EXISTING LONG-TERM]\n{lt_text}\n\n[MEDIUM-TERM TO MERGE]\n{mt_text}")
            
            try:
                resp = llm.invoke([sys_msg, user_msg])
                lt_covered = (long_term["turns_covered"] if long_term else 0) + medium_term["turns_covered"]
                long_term = {
                    "memory_tier": "long_term",
                    "summary": resp.content.strip(),
                    "turns_covered": lt_covered
                }
                medium_term = None  # Reset medium term since it flushed into long term
                updated = True
            except Exception as e:
                print(f"⚠️ [Memory] Failed Long-Term decay: {e}")

        # 2. Short-Term -> Medium-Term Decay
        if len(uncompressed) >= raw_threshold:
            print(f"🗜️  [Memory] Decaying: Moving oldest {batch_size} Short-Term turns to Medium-Term for {agent_name}...")
            oldest_batch = uncompressed[:batch_size]
            uncompressed = uncompressed[batch_size:]  # Keep the rest as short-term raw
            
            mt_text = medium_term["summary"] if medium_term else "None."
            
            lines = []
            for i, turn in enumerate(oldest_batch, start=1):
                received = turn.get("task_received")
                delegated = turn.get("tasks_delegated", [])
                lines.append(f"TURN {i}:")
                if received:
                    lines.append(f"  Received: {received.get('task_instructions')}")
                    lines.append(f"  Responded: {received.get('response_provided')}")
                for d in delegated:
                    lines.append(f"  Delegated: {d.get('task_delivered')} -> {d.get('task_response')}")
            raw_text = "\n".join(lines)
            
            sys_msg = SystemMessage(content=(
                f"You are the memory subsystem for the AI agent '{agent_name}'.\n"
                "Merge the existing MEDIUM-TERM memory with {batch_size} newly decayed SHORT-TERM turns.\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. Compress down to ~50% size. Maintain bullet points of what files were touched and key actions taken.\n"
                "2. Retain technical continuity but drop verbose conversational fluff.\n"
                "3. Format as a dense technical log."
            ))
            user_msg = HumanMessage(content=f"[EXISTING MEDIUM-TERM]\n{mt_text}\n\n[NEW TURNS TO MERGE]\n{raw_text}")
            
            try:
                resp = llm.invoke([sys_msg, user_msg])
                mt_covered = (medium_term["turns_covered"] if medium_term else 0) + batch_size
                medium_term = {
                    "memory_tier": "medium_term",
                    "summary": resp.content.strip(),
                    "turns_covered": mt_covered
                }
                updated = True
            except Exception as e:
                print(f"⚠️ [Memory] Failed Medium-Term decay: {e}")
                uncompressed = oldest_batch + uncompressed # Revert on failure
                updated = False

    if updated:
        # Rebuild history with strict ordering: Long -> Medium -> Short
        new_history = []
        if long_term: new_history.append(long_term)
        if medium_term: new_history.append(medium_term)
        new_history.extend(uncompressed)
        return new_history
        
    return existing_history


# ─────────────────────────────────────────────────────────────────────────────
# WRITE — Persist one turn's execution record to Redis
# ─────────────────────────────────────────────────────────────────────────────

def persist_turn(session_id: str, team_execution_report: dict) -> None:
    """
    Append the current turn's execution records to Redis for every agent.
    Auto-triggers decaying compression if thresholds are met.
    """
    timestamp = _utc_now()

    for agent_name, record in team_execution_report.items():
        key = _redis_key(session_id, agent_name)

        task_received_entry = None
        if record.task_received:
            task_received_entry = {
                "timestamp": timestamp,
                "supervisor": record.task_received.supervisor,
                "task_instructions": record.task_received.task_instructions,
                "response_provided": record.task_received.response_provided,
            }

        tasks_delegated_entries = []
        for delegation in record.tasks_delegated:
            tasks_delegated_entries.append({
                "timestamp": timestamp,
                "subordinate_agent": delegation.subordinate_agent,
                "task_delivered": delegation.task_delivered,
                "task_response": delegation.task_response,
            })

        turn_entry = {
            "task_received": task_received_entry,
            "tasks_delegated": tasks_delegated_entries,
        }

        # Append to existing
        existing_raw = _redis.get(key)
        if existing_raw:
            existing: list = json.loads(existing_raw.decode("utf-8"))
        else:
            existing = []

        existing.append(turn_entry)
        
        # Trigger Decaying Memory Compression
        existing = _compress_history(agent_name, existing)
        
        _redis.set(key, json.dumps(existing))


# ─────────────────────────────────────────────────────────────────────────────
# READ — Load an agent's full history from Redis
# ─────────────────────────────────────────────────────────────────────────────

def load_agent_history(session_id: str, agent_name: str) -> Optional[str]:
    """
    Load the full execution history for a single agent from Redis.
    Formats the 3-tier Decaying Memory cleanly for the LLM prompt.
    """
    key = _redis_key(session_id, agent_name)
    raw = _redis.get(key)
    if not raw:
        return None

    history: list = json.loads(raw.decode("utf-8"))
    if not history:
        return None

    lines = []
    turn_counter = 1
    
    for turn in history:
        tier = turn.get("memory_tier")
        
        if tier == "long_term":
            lines.append(f"🏛️ LONG-TERM MEMORY (Covers {turn['turns_covered']} oldest turns):")
            lines.append(f"{turn['summary']}\n")
            turn_counter += turn["turns_covered"]
            continue
            
        elif tier == "medium_term":
            lines.append(f"📚 MEDIUM-TERM MEMORY (Covers {turn['turns_covered']} older turns):")
            lines.append(f"{turn['summary']}\n")
            turn_counter += turn["turns_covered"]
            continue
            
        elif "compressed_summary" in turn: # Legacy support
            lines.append(f"🧠 COMPRESSED HISTORY (Covers {turn.get('turns_covered', '?')} turns):")
            lines.append(f"{turn['compressed_summary']}\n")
            turn_counter += turn.get("turns_covered", 10)
            continue
            
        # Handle Short-Term / Raw Uncompressed Turns
        received = turn.get("task_received")
        delegated = turn.get("tasks_delegated", [])

        ts = received.get("timestamp", "?") if received else "?"
        lines.append(f"TURN {turn_counter} ({ts}):")

        if received:
            lines.append(f"  Received from {received['supervisor']}: \"{received['task_instructions']}\"")
            lines.append(f"  Responded: \"{received['response_provided']}\"")

        for d in delegated:
            lines.append(f"  Delegated to {d['subordinate_agent']}: \"{d['task_delivered']}\"")
            lines.append(f"    → Response: \"{d['task_response']}\"")

        lines.append("")
        turn_counter += 1

    return "\n".join(lines).strip()


# ─────────────────────────────────────────────────────────────────────────────
# CLEAR — Wipe all execution history for a session (use carefully)
# ─────────────────────────────────────────────────────────────────────────────

def clear_session_history(session_id: str) -> None:
    """
    Deletes all execution_history keys for the given session.
    """
    keys = _redis.keys(f"execution_history:{session_id}:*")
    if keys:
        _redis.delete(*keys)

def persist_tool_report(session_id: str, team_tool_report: dict) -> None:
    """
    Save the live team_tool_report to Redis for crash recovery and future sessions.
    """
    key = f"team_tool_report:{session_id}"
    dumped = {}
    for agent, report in team_tool_report.items():
        if hasattr(report, "model_dump"):
            dumped[agent] = report.model_dump()
        elif hasattr(report, "dict"):
            dumped[agent] = report.dict()
        else:
            dumped[agent] = report
    _redis.set(key, json.dumps(dumped))

def load_tool_report(session_id: str) -> dict:
    """
    Load the team_tool_report from Redis.
    """
    key = f"team_tool_report:{session_id}"
    raw = _redis.get(key)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))
