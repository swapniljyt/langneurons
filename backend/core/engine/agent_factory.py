"""
core/engine/agent_factory.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LangNeurons Freeze Phase — Universal Agent Executor.

neural_agent(agent_name, state, session_id, root_node) is the single function
that drives ALL agent execution during the freeze phase.

Flow per agent invocation:
  A. Build context (skill + team_tool_report + Redis history + task_received)
  B. Routing LLM call → AgentDecision (delegate / use_tool / respond)
  C. Sequential delegation loop (one subordinate at a time)
  D. Tool execution via ReAct agent (if action == "use_tool")
  E. Fill response_provided, return state upward

State contract:
  - task_received.response_provided starts as "pending"
  - Set to "in_progress" when agent begins
  - Set to final response string when agent finishes
  - team_execution_report is NEVER parallel — one agent active at a time
  - team_tool_report is NEVER flushed — grows with timestamps across all turns
"""

from __future__ import annotations

import json
import os
import asyncio
from datetime import datetime, timezone
from typing import Literal, List, Optional

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field, model_validator

from ..state.langneural_state import (
    LangneuralState,
    AgentExecutionRecord,
    AssignedTask,
    TaskDelegation,
    AgentToolReport,
    ReadAction,
    WriteAction,
    EditAction,
    ErrorAction,
)
from ..engine.memory import RedisClient
from ..memory.execution_memory import load_agent_history


# ─────────────────────────────────────────────────────────────────────────────
# Redis client (module-level singleton)
# ─────────────────────────────────────────────────────────────────────────────

_redis_instance = RedisClient()
_redis = _redis_instance.get_client()

# ─────────────────────────────────────────────────────────────────────────────
# Tracks files already live-streamed so intercept_file_write skips re-animation
# ─────────────────────────────────────────────────────────────────────────────

_already_streamed_paths: set = set()

# When False, thinking is disabled for ALL agents regardless of agent_type.
# Set via set_global_thinking(False) from run_swarm before execution.
_GLOBAL_THINKING_ENABLED: bool = True


def print_telemetry(msg: str) -> None:
    """Print message wrapped in telemetry tags for the frontend parser."""
    print(f"<telemetry_log>{msg}</telemetry_log>", flush=True)


def set_global_thinking(enabled: bool) -> None:
    """Toggle thinking mode globally. Call before kicking off neural_agent."""
    global _GLOBAL_THINKING_ENABLED
    _GLOBAL_THINKING_ENABLED = enabled
    if not enabled:
        print_telemetry("  💤 [LangNeurons] Thinking mode DISABLED for all agents.")
    else:
        print_telemetry("  🧠 [LangNeurons] Thinking mode ENABLED.")


class _StreamingFileWriter:
    """
    Intercepts write_file tool-call argument chunks AS they stream from the LLM
    and writes the content field to disk token-by-token — so the file grows in
    the editor in real time while the model is still generating, not after.

    JSON content escapes (\\n, \\", etc.) are decoded on the fly.
    A status line is printed periodically so the terminal never looks stuck.
    """

    WRITE_TOOLS = {"write_file"}   # namespaced tool is also named write_file

    def __init__(self, agent_label: str):
        self._label = agent_label
        self._active: dict = {}   # tc_id -> state dict

    # ── public API ────────────────────────────────────────────────────────

    def feed(self, tool_call_chunks: list) -> None:
        """Call with msg.tool_call_chunks from each streamed AIMessageChunk."""
        import re
        for chunk in tool_call_chunks:
            tc_id  = str(chunk.get("id") or chunk.get("index", 0))
            name   = chunk.get("name") or ""
            args_t = chunk.get("args") or ""

            if name in self.WRITE_TOOLS:
                if tc_id not in self._active:
                    self._active[tc_id] = {
                        "buf": "", "filepath": None, "fh": None,
                        "content_started": False, "esc_pending": False,
                        "chars": 0, "lines": 0,
                    }

            s = self._active.get(tc_id)
            if s is None:
                continue

            s["buf"] += args_t

            # Phase 1 — extract filepath from accumulated JSON
            if s["filepath"] is None:
                m = re.search(r'"filepath"\s*:\s*"([^"\\]+)"', s["buf"])
                if m:
                    from ..tools.filesystem.read_write import _get_sandboxed_path, SANDBOX_DIR
                    s["filepath"] = m.group(1)
                    try:
                        tgt = _get_sandboxed_path(s["filepath"])
                        os.makedirs(os.path.dirname(tgt), exist_ok=True)
                        s["fh"] = open(tgt, "w", encoding="utf-8")
                        print_telemetry(
                            f"  ⌨  [{self._label}] LIVE streaming → "
                            f"sandbox/{os.path.relpath(tgt, SANDBOX_DIR)}"
                        )
                    except Exception as exc:
                        print_telemetry(f"  ⚠️  StreamingFileWriter open error: {exc}")
                        s["fh"] = None

            # Phase 2 — extract & write content tokens
            if s["fh"] and args_t:
                decoded = self._extract(s, args_t)
                if decoded:
                    s["fh"].write(decoded)
                    s["fh"].flush()
                    s["chars"] += len(decoded)
                    s["lines"] += decoded.count("\n")
                    # Status every 50 lines
                    if s["lines"] % 50 == 0 and s["lines"] > 0:
                        print_telemetry(
                            f"  ⌨  [{self._label}] "
                            f"{s['filepath']} — {s['chars']:,} chars | {s['lines']} lines"
                        )

    def close_all(self) -> None:
        """Close file handles and register streamed paths."""
        from ..tools.filesystem.read_write import _get_sandboxed_path
        for s in self._active.values():
            if s.get("fh"):
                try:
                    s["fh"].close()
                except Exception:
                    pass
            if s.get("filepath"):
                try:
                    _already_streamed_paths.add(
                        _get_sandboxed_path(s["filepath"])
                    )
                    print_telemetry(
                        f"  ✅ [{self._label}] Streamed {s['chars']:,} chars → "
                        f"{s['filepath']}"
                    )
                except Exception:
                    pass

    # ── internal JSON-escape decoder ──────────────────────────────────────

    def _extract(self, s: dict, chunk: str) -> str:
        """Decode the content field value from a streaming JSON args chunk."""
        out = []
        i   = 0

        if not s["content_started"]:
            marker = s["buf"].find('"content":') 
            if marker == -1:
                return ""
            # Find the opening quote of the value
            q = s["buf"].find('"', marker + len('"content":'))
            if q == -1:
                return ""
            s["content_started"] = True
            # Recalculate how far into `chunk` the content starts
            content_abs = q + 1   # absolute index into s["buf"]
            buf_before  = len(s["buf"]) - len(chunk)
            i = max(0, content_abs - buf_before)

        while i < len(chunk):
            if s["esc_pending"]:
                c = chunk[i]
                out.append({'n':'\n','t':'\t','r':'\r','"':'"','\\':'\\','/':'/'}.get(c, '\\'+c))
                s["esc_pending"] = False
                i += 1
            elif chunk[i] == '\\':
                if i + 1 < len(chunk):
                    c = chunk[i+1]
                    out.append({'n':'\n','t':'\t','r':'\r','"':'"','\\':'\\','/':'/'}.get(c,'\\'+c))
                    i += 2
                else:
                    s["esc_pending"] = True
                    i += 1
            elif chunk[i] == '"':   # closing quote = end of content
                break
            else:
                out.append(chunk[i])
                i += 1

        return "".join(out)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _agent_label(common_name: str, root_node=None) -> str:
    """
    Returns 'common_name (dynamic_name)' if the dynamic_name is known and different,
    otherwise just returns the common_name.
    Used for all console snapshots and routing context so the identity is always clear.
    """
    if root_node is None:
        return common_name
    node = root_node.find_neuron_by_name(common_name)
    if node and node.dynamic_name and node.dynamic_name != common_name:
        return f"{common_name} ({node.dynamic_name})"
    return common_name


# ─────────────────────────────────────────────────────────────────────────────
# Static OS Prompt — injected into every agent, loaded from os_prompt.md
# ─────────────────────────────────────────────────────────────────────────────

from ..utils.prompt_loader import PromptLoader
from ..engine.prompt_builder import build_agent_prompt

# ─────────────────────────────────────────────────────────────────────────────
# AgentDecision — structured output from routing LLM call
# ─────────────────────────────────────────────────────────────────────────────

class DelegationItem(BaseModel):
    subordinate: str = Field(description="The common_name of the subordinate agent to delegate to.")
    task: str = Field(
        description=(
            "Detailed task instructions for this subordinate. "
            "Include relevant context from team_tool_report and prior work so they can act immediately."
        )
    )


class AgentDecision(BaseModel):
    """Structured routing decision output from the LLM."""
    action: Literal["delegate", "use_tool", "respond"] = Field(
        description=(
            "delegate — send task(s) to subordinate(s) sequentially. "
            "use_tool — execute tools directly to complete this task. "
            "respond — return a final answer (no delegation, no tools needed)."
        )
    )
    delegation_plan: List[DelegationItem] = Field(
        default_factory=list,
        description=(
            "Ordered list of delegations to execute SEQUENTIALLY. "
            "First item executes first. Only populated when action='delegate'."
        )
    )
    tool_instructions: str = Field(
        default="",
        description=(
            "Specific instructions for what tools to use and what to produce. "
            "Only populated when action='use_tool'."
        )
    )
    response: str = Field(
        default="",
        description=(
            "Final response to return to the supervisor. "
            "Populated for action='respond', and as summary after 'delegate' or 'use_tool'."
        )
    )

    @model_validator(mode="before")
    @classmethod
    def clean_fields(cls, data):
        if isinstance(data, dict):
            # Clean action string from any quotes, brackets, or leading/trailing whitespace
            if "action" in data and isinstance(data["action"], str):
                cleaned = data["action"].strip(" \t\n\r\"'[]()")
                if cleaned in ("delegate", "use_tool", "respond"):
                    data["action"] = cleaned
                else:
                    # Fuzzy match fallback
                    for option in ("delegate", "use_tool", "respond"):
                        if option in cleaned:
                            data["action"] = option
                            break
            # Clean delegation plan subordinate names from any trailing/leading quotes/spaces
            if "delegation_plan" in data and isinstance(data["delegation_plan"], list):
                for item in data["delegation_plan"]:
                    if isinstance(item, dict) and "subordinate" in item and isinstance(item["subordinate"], str):
                        item["subordinate"] = item["subordinate"].strip(" \t\n\r\"'[]()")
        return data


# ─────────────────────────────────────────────────────────────────────────────
# (Tool report formatter and skill loader moved to prompt_builder.py)
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# MAIN — neural_agent
# ─────────────────────────────────────────────────────────────────────────────

async def neural_agent(
    agent_name: str,
    state: LangneuralState,
    session_id: str,
    root_node=None,
) -> LangneuralState:
    """
    Universal agent executor for the LangNeurons freeze phase.

    Takes state, reads this agent's task from it, makes a routing decision,
    executes sequentially (delegate or tool), fills response, returns state.

    Args:
        agent_name:  The common_name of the agent to execute.
        state:       The shared LangneuralState — single source of truth.
        session_id:  Redis session key for history and skill files.
        root_node:   The AgentNode tree root (used for tool resolution).

    Returns:
        Updated LangneuralState with this agent's response_provided filled.
    """
    from ..llm.connector import LLMConnector

    # ── Mark as in_progress ────────────────────────────────────────────────
    if agent_name not in state.team_execution_report:
        state.team_execution_report[agent_name] = AgentExecutionRecord()

    record = state.team_execution_report[agent_name]
    if record.task_received:
        record.task_received.response_provided = "in_progress"

    task_instructions = (
        record.task_received.task_instructions
        if record.task_received
        else "No task assigned."
    )
    supervisor = record.task_received.supervisor if record.task_received else "unknown"

    print_telemetry(f"🧠 [{_agent_label(agent_name, root_node)}] Activated by {_agent_label(supervisor, root_node)} | Task: {task_instructions[:80]}...")

    # ── A. Build unified 9-section system prompt ──────────────────────────

    hierarchy = state.agent_hierarchy.get(agent_name)
    subordinates_list = hierarchy.subordinates if hierarchy else []
    my_tools_list = state.agent_tools.get(agent_name, [])
    my_history = load_agent_history(session_id, agent_name)

    # Find the live AgentNode so prompt_builder can walk the tree
    agent_node_obj = root_node.find_neuron_by_name(agent_name) if root_node else None

    if agent_node_obj is not None:
        # Use the rich tree-aware builder
        full_system_prompt = build_agent_prompt(
            agent_node=agent_node_obj,
            session_id=session_id,
            current_task=task_instructions,
            supervisor_name=supervisor,
            team_tool_report=state.team_tool_report,
            conversation_history=my_history,
            tool_names=my_tools_list,
            team_execution_report=state.team_execution_report,
        )
    else:
        # Fallback: node not found — build minimal prompt from os_prompt.md
        from ..modules.skill_generator import SkillGenerator
        gen = SkillGenerator(llm_client=None)
        persona_task = gen.load_system_prompt_from_file(agent_name, session_id) or f"You are {agent_name}."
        full_system_prompt = PromptLoader.get_prompt("system/os_prompt.md", persona_task=persona_task)

    is_human_facing = (supervisor == "human")
    is_leaf = not bool(subordinates_list)

    routing_context = (
        f"CURRENT TASK\n"
        f"Assigned by : {_agent_label(supervisor, root_node)}\n"
        f"Task        : {task_instructions}\n\n"
        f"YOUR IDENTITY: You are {_agent_label(agent_name, root_node)}.\n"
        f"  - common_name  = '{agent_name}' (your stable system identifier, used for delegation)\n"
        f"  - dynamic_name = '{agent_node_obj.dynamic_name if agent_node_obj and agent_node_obj.dynamic_name else 'not yet assigned'}' (your role title, based on your skill)\n\n"
        f"Read your system prompt sections carefully, then output a JSON object "
        f"with EXACTLY these fields:\n"
        f"{{\n"
        f'  "action": "delegate" | "use_tool" | "respond",\n'
        f'  "delegation_plan": [  // only when action=delegate\n'
        f'    {{"subordinate": "<common_name>", "task": "<detailed task instructions>"}}\n'
        f'  ],\n'
        f'  "tool_instructions": "<what to do with tools>",  // only when action=use_tool\n'
        f'  "response": "<your final message>"  // ALWAYS fill this\n'
        f"}}\n\n"
        f"CRITICAL for the 'response' field:\n"
    )
    if is_human_facing:
        routing_context += (
            f"  You are talking to a HUMAN. The 'response' field is what they see.\n"
            f"  Write it conversationally. Never expose agent names, JSON, or internal workflow.\n"
            f"  After delegation: summarise the outcome in plain, friendly language.\n"
        )
    else:
        routing_context += (
            f"  You are reporting back to {supervisor} (an AI agent).\n"
            f"  Write a plain-text summary of what you did and what the result is.\n"
            f"  Never return raw JSON in this field.\n"
        )

    # ── B. Routing LLM call ────────────────────────────────────────────────

    router_llm = LLMConnector.get_llm(purpose="router", temperature=0.1)
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "openai":
        structured_router = router_llm.with_structured_output(AgentDecision, method="function_calling")
    else:
        structured_router = router_llm.with_structured_output(AgentDecision)

    messages = [
        SystemMessage(content=full_system_prompt),
        HumanMessage(content=routing_context),
    ]

    # Initialize LangTrace Callback Handler
    from core.langtrace import LangTraceCallbackHandler
    from core.engine.prompt_builder import _load_skill, _format_tool_report
    
    formatted_tool_report = _format_tool_report(state.team_tool_report, state.team_execution_report)
    
    trace_handler = LangTraceCallbackHandler(
        session_id=session_id,
        agent_name=agent_name,
        purpose="router",
        system_prompt=full_system_prompt,
        skill=_load_skill(agent_name, session_id),
        conversation_history=my_history or "",
        tool_report=formatted_tool_report,
        execution_report=state.team_execution_report,
        routing_context=routing_context,
    )

    try:
        decision: AgentDecision = await structured_router.ainvoke(
            messages,
            config={"callbacks": [trace_handler]}
        )
    except Exception as e:
        print_telemetry(f"  ⚠️ [{agent_name}] Structured routing LLM failed: {e}. Attempting JSON fallback...")
        try:
            # Fallback: Query the base router LLM directly and ask for JSON schema compliance
            fallback_messages = [
                SystemMessage(content=full_system_prompt + "\n\nCRITICAL: You must output a valid JSON object matching this schema:\n" + json.dumps(AgentDecision.model_json_schema(), indent=2)),
                HumanMessage(content=routing_context + "\n\nReturn ONLY a raw JSON object matching the schema. Do not include any explanations or conversational text outside the JSON. Do not include markdown code block formatting (like ```json)."),
            ]
            fallback_res = await router_llm.ainvoke(
                fallback_messages,
                config={"callbacks": [trace_handler]}
            )
            # Parse the JSON response
            content = fallback_res.content.strip()
            if content.startswith("```"):
                # strip markdown blocks
                lines = content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()
            
            parsed_json = json.loads(content)
            decision = AgentDecision(**parsed_json)
            print_telemetry(f"  ✅ [{agent_name}] JSON fallback successfully parsed!")
        except Exception as fallback_err:
            print_telemetry(f"  ❌ [{agent_name}] JSON fallback also failed: {fallback_err}")
            decision = AgentDecision(
                action="respond",
                response=f"[{agent_name}] encountered a routing error: {e}",
            )

    print_telemetry(f"  📋 [{_agent_label(agent_name, root_node)}] Decision: {decision.action}"
          + (f" → {[_agent_label(d.subordinate, root_node) for d in decision.delegation_plan]}" if decision.delegation_plan else ""))

    # ── C. Sequential delegation ───────────────────────────────────────────

    if decision.action == "delegate" and decision.delegation_plan:
        for item in decision.delegation_plan:
            subordinate = item.subordinate
            task = item.task

            # Validate subordinate is in our hierarchy
            if subordinate not in subordinates_list:
                print_telemetry(f"  ⚠️ [{agent_name}] Tried to delegate to unknown subordinate '{subordinate}'. Skipping.")
                continue

            # Open delegation slot (pending)
            delegation_entry = TaskDelegation(
                timestamp=_utc_now(),
                subordinate_agent=subordinate,
                task_delivered=task,
                task_response="pending",
            )
            record.tasks_delegated.append(delegation_entry)

            # Fill subordinate inbox
            if subordinate not in state.team_execution_report:
                state.team_execution_report[subordinate] = AgentExecutionRecord()
            state.team_execution_report[subordinate].task_received = AssignedTask(
                supervisor=agent_name,
                task_instructions=task,
                response_provided="pending",
            )

            print_telemetry(f"  ➡️  [{_agent_label(agent_name, root_node)}] Delegating to {_agent_label(subordinate, root_node)}...")

            # Recursive call — sequential, state passed down and back up
            state = await neural_agent(subordinate, state, session_id, root_node)

            # Read response back from subordinate's inbox
            sub_record = state.team_execution_report.get(subordinate)
            response_back = (
                sub_record.task_received.response_provided
                if sub_record and sub_record.task_received
                else "No response received."
            )

            # Close delegation slot
            delegation_entry.task_response = response_back
            print_telemetry(f"  ✅ [{_agent_label(agent_name, root_node)}] {_agent_label(subordinate, root_node)} responded: {response_back[:60]}...")

        # Build final response
        # 1. Start with the supervisor's message (e.g. "I have delegated this to Neuron2")
        final_response_parts = []
        if decision.response and decision.response.strip():
            final_response_parts.append(decision.response.strip())

        # 2. Append the actual results returned by the subordinates!
        sub_summaries = []
        for d in record.tasks_delegated:
            sub_resp = d.task_response or "(no response)"
            # Strip raw JSON if leaked — extract response_provided text if possible
            if sub_resp.strip().startswith("{"):
                try:
                    parsed = json.loads(sub_resp)
                    sub_resp = (
                        parsed.get("task_received", {}).get("response_provided")
                        or parsed.get("response", "")
                        or sub_resp
                    )
                except Exception:
                    pass
            sub_summaries.append(sub_resp)
            
        if sub_summaries:
            if is_human_facing:
                # Human-facing: combine into clean paragraph
                combined = "\n\n".join(s for s in sub_summaries if s)
                if combined:
                    final_response_parts.append(f"\n\n[Findings]:\n{combined}")
            else:
                combined = "\n\n".join(s for s in sub_summaries if s)
                if combined:
                    final_response_parts.append(f"\n\n[Subordinate Report]:\n{combined}")
                    
        final_response = "".join(final_response_parts)

    # ── D. Tool execution ──────────────────────────────────────────────────

    elif decision.action == "use_tool":
        final_response = await _execute_tools(
            agent_name=agent_name,
            state=state,
            session_id=session_id,
            task_instructions=task_instructions,
            tool_instructions=decision.tool_instructions,
            full_system_prompt=full_system_prompt,
            root_node=root_node,
        )

    # ── Respond directly ───────────────────────────────────────────────────

    else:
        final_response = decision.response or f"[{agent_name}] task acknowledged."

    # ── E. Fill response and return state ─────────────────────────────────

    if record.task_received:
        record.task_received.response_provided = final_response

    print_telemetry(f"  ✔️  [{_agent_label(agent_name, root_node)}] Complete. Response: {final_response[:80]}...")
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Tool execution via ReAct agent
# ─────────────────────────────────────────────────────────────────────────────

async def _execute_tools(
    agent_name: str,
    state: LangneuralState,
    session_id: str,
    task_instructions: str,
    tool_instructions: str,
    full_system_prompt: str,
    root_node=None,
) -> str:
    """
    Spin up a ReAct tool-calling agent for this agent and run it.
    Updates state.team_tool_report[agent_name] with timestamped entries.
    Returns a summary string of what was accomplished.
    """
    # ── Resolve agent_type to enable selective thinking ──────────────────────
    agent_node_ref = root_node.find_neuron_by_name(agent_name) if root_node else None
    agent_type_str = (
        getattr(agent_node_ref, "agent_type", "") or ""
        if agent_node_ref else ""
    )

    from ..llm.connector import LLMConnector, is_thinking_agent
    
    thinking_active = is_thinking_agent(agent_type_str)
    if thinking_active:
        print_telemetry(
            f"  🧠💡 [{_agent_label(agent_name, root_node)}] "
            f"Thinking mode ON (agent_type='{agent_type_str}')"
        )

    # ── Resolve tools from root_node tree ─────────────────────────────────
    tools = _resolve_tools(agent_name, root_node)
    if not tools:
        return f"[{agent_name}] No tools available to execute task."

    # Wrap tools with Rich status animation
    import copy
    from rich.console import Console
    console = Console()
    wrapped_tools = []
    lbl = _agent_label(agent_name, root_node)
    
    for t in tools:
        t_copy = copy.copy(t)
        orig_invoke = t_copy.invoke
        orig_ainvoke = t_copy.ainvoke
        t_name = t.name
        
        def make_invoke(original_func, name_str):
            def wrapped_invoke(*args, **kwargs):
                with console.status(f"[bold yellow]⚙️  {lbl} is using tool '{name_str}'...[/bold yellow]"):
                    return original_func(*args, **kwargs)
            return wrapped_invoke

        def make_ainvoke(original_func, name_str):
            async def wrapped_ainvoke(*args, **kwargs):
                with console.status(f"[bold yellow]⚙️  {lbl} is using tool '{name_str}'...[/bold yellow]"):
                    return await original_func(*args, **kwargs)
            return wrapped_ainvoke

        object.__setattr__(t_copy, "invoke", make_invoke(orig_invoke, t_name))
        object.__setattr__(t_copy, "ainvoke", make_ainvoke(orig_ainvoke, t_name))
        wrapped_tools.append(t_copy)

    # ── Build ReAct agent ──────────────────────────────────────────────────
    tool_llm = LLMConnector.get_llm(
        purpose="execution",
        agent_type=agent_type_str,
    )
    checkpointer = MemorySaver()
    react_agent = create_react_agent(
        model=tool_llm,
        tools=wrapped_tools,
        checkpointer=checkpointer,
        prompt=full_system_prompt,
    )

    execution_prompt = (
        f"TASK:\n{task_instructions}\n\n"
        f"EXECUTION INSTRUCTIONS:\n{tool_instructions}\n\n"
        "══════════════════════════════════════════════════\n"
        "MANDATORY: You MUST call at least one tool before responding. "
        "Do NOT describe what you plan to do — just DO IT using your tools. "
        "After all tool calls are complete, write a factual summary of what "
        "the tools returned, including file paths, sizes, and any errors. "
        "Your supervisor CANNOT see tool outputs — include ALL findings in your final message. "
        "Do NOT output JSON. Write a natural language report."
        "══════════════════════════════════════════════════"
    )

    from core.langtrace import LangTraceCallbackHandler
    from core.engine.prompt_builder import _load_skill, _format_tool_report
    
    formatted_tool_report = _format_tool_report(state.team_tool_report, state.team_execution_report)
    my_history = load_agent_history(session_id, agent_name) or ""
    
    trace_handler = LangTraceCallbackHandler(
        session_id=session_id,
        agent_name=agent_name,
        purpose="execution",
        system_prompt=full_system_prompt,
        skill=_load_skill(agent_name, session_id),
        conversation_history=my_history,
        tool_report=formatted_tool_report,
        execution_report=state.team_execution_report,
        routing_context=execution_prompt,
    )

    config = {
        "configurable": {"thread_id": f"{session_id}::{agent_name}"},
        "callbacks": [trace_handler]
    }

    # ── Run tool loop ──────────────────────────────────────────────────────
    timestamp = _utc_now()
    final_content = ""
    files_written = []
    files_edited = []
    commands_run = []
    errors = []
    data_gathered = []

    HALLUCINATION_WARNING = (
        "\n\n⚠️  ALERT: You responded without calling ANY tool. "
        "This is NOT acceptable. You MUST call the appropriate tool right now. "
        "Do not explain, do not summarise — just call the tool."
    )
    MAX_TOOL_RETRIES = 2

    try:
        lbl = _agent_label(agent_name, root_node)

        async def _run_agent_stream(input_messages):
            if thinking_active:
                print(f"<thinking_start agent=\"{lbl}\" />\n", end="", flush=True)

            streamer = _StreamingFileWriter(lbl)
            final_messages = []

            async for event_type, event_data in react_agent.astream(
                {"messages": input_messages}, config,
                stream_mode=["messages", "values"]
            ):
                if event_type == "messages":
                    msg, _ = event_data
                    # ── Reasoning output (thinking models) ────────────────
                    if hasattr(msg, "additional_kwargs"):
                        r = msg.additional_kwargs.get("reasoning_content")
                        if r and thinking_active:
                            print(f"<thinking_token>{r}</thinking_token>\n", end="", flush=True)
                    # ── Live-stream write_file content to disk ─────────────
                    tcc = getattr(msg, "tool_call_chunks", None)
                    if tcc:
                        streamer.feed(tcc)

                elif event_type == "values":
                    final_messages = event_data.get("messages", [])

            streamer.close_all()   # flush + register streamed paths

            if thinking_active:
                print("<thinking_end />\n", end="", flush=True)
            return final_messages

        messages = await _run_agent_stream([("user", execution_prompt)])

        # ── Hallucination guard: ensure at least one tool was actually called ──
        def _has_tool_call(msgs) -> bool:
            return any(
                (hasattr(m, "type") and m.type == "tool")
                for m in msgs
            )

        retry_count = 0
        while not _has_tool_call(messages) and retry_count < MAX_TOOL_RETRIES:
            retry_count += 1
            print_telemetry(f"  ⚠️  [{_agent_label(agent_name, root_node)}] No tool called — retry {retry_count}/{MAX_TOOL_RETRIES}")
            messages = await _run_agent_stream([
                ("user", execution_prompt),
                ("assistant", messages[-1].content if messages else ""),
                ("user", HALLUCINATION_WARNING),
            ])

        if not _has_tool_call(messages):
            print_telemetry(f"  ❌  [{_agent_label(agent_name, root_node)}] Agent refused to call tools after {MAX_TOOL_RETRIES} retries.")

        for msg in messages:
            # Track explicit tool execution results (ToolMessage)
            if hasattr(msg, "type") and msg.type == "tool":
                tool_name = getattr(msg, "name", "unknown")
                if any(kw in tool_name for kw in ("read", "list", "search", "get", "ask", "confirm")):
                    content = msg.content
                    if len(content) > 500:
                        content = content[:500] + "..."
                    data_gathered.append(f"Result from {tool_name}: {content}")

            # Track AI tool intents and file operations
            if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                continue
            for tc in msg.tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})

                # Track commands
                cmd = tool_args.get("command") or tool_args.get("cmd")
                if cmd:
                    commands_run.append(cmd)

                # Track writes
                if any(kw in tool_name for kw in ("write", "create", "save", "generate")):
                    path = (
                        tool_args.get("filepath") or tool_args.get("path")
                        or tool_args.get("file_path") or tool_args.get("filename") or ""
                    )
                    content = tool_args.get("content", "")
                    description = tool_args.get("description", f"Written by {agent_name}")
                    if path:
                        from ..state.langneural_state import FileWriteData
                        files_written.append(FileWriteData(
                            file_path=path,
                            description=description,
                            content=content[:500],  # truncate for state
                        ))

                # Track edits
                if any(kw in tool_name for kw in ("edit", "patch", "modify", "update")):
                    path = (
                        tool_args.get("filepath") or tool_args.get("path")
                        or tool_args.get("file_path") or ""
                    )
                    if path:
                        from ..state.langneural_state import FileEditData
                        files_edited.append(FileEditData(
                            file_path=path,
                            edit_description=tool_args.get("description", f"Edited by {agent_name}"),
                        ))

        # Extract final AI message + accumulate token usage
        total_in = 0
        total_out = 0
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                final_content = msg.content
                break

        # ── Token usage: read from every AI message in this tool-call session ──
        for msg in messages:
            if not (hasattr(msg, "type") and msg.type == "ai"):
                continue
            meta = getattr(msg, "usage_metadata", None) or getattr(msg, "response_metadata", {}).get("token_usage", {})
            if isinstance(meta, dict):
                total_in  += meta.get("input_tokens",  0) or meta.get("prompt_tokens",     0)
                total_out += meta.get("output_tokens", 0) or meta.get("completion_tokens", 0)

        if total_in or total_out:
            print_telemetry(
                f"  📊 [{_agent_label(agent_name, root_node)}] Tool tokens — "
                f"in:{total_in} out:{total_out} total:{total_in + total_out}"
            )

    except Exception as e:
        errors.append({
            "tool": "react_agent",
            "error": str(e),
        })
        final_content = f"[{agent_name}] Tool execution failed: {e}"
        print_telemetry(f"  ⚠️ [{agent_name}] Tool execution error: {e}")

    # ── Update team_tool_report ────────────────────────────────────────────
    if agent_name not in state.team_tool_report:
        state.team_tool_report[agent_name] = AgentToolReport()

    report = state.team_tool_report[agent_name]

    if data_gathered:
        # SANITIZATION: Truncate massive read strings and deduplicate
        sanitized_data = []
        for d in data_gathered:
            clean = str(d).strip().replace('\n', ' ')
            if len(clean) > 150:
                clean = clean[:147] + "..."
            sanitized_data.append(clean)
        # Deduplicate while preserving order
        unique_data = list(dict.fromkeys(sanitized_data))

        report.read.append(ReadAction(
            timestamp=timestamp,
            tools_used=["read_file"],
            commands_executed=[],
            data_gathered=unique_data,
        ))
        # Sliding Window: Keep only last 20 reads
        report.read = report.read[-20:]

    if files_written:
        # SANITIZATION: Strip out raw source code to prevent context window explosion.
        # The file is safely on disk, so other agents can read it if they need to.
        for fw in files_written:
            fw.content = "(Content omitted. Use read_file to view if needed.)"

        report.write.append(WriteAction(
            timestamp=timestamp,
            tools_used=["write_file"],
            commands_executed=commands_run,
            files_written=files_written,
        ))
        # Sliding Window: Keep only last 20 writes
        report.write = report.write[-20:]

    if files_edited:
        report.edited.append(EditAction(
            timestamp=timestamp,
            tools_used=["edit_file_patch"],
            commands_executed=commands_run,
            files_edited=files_edited,
        ))
        # Sliding Window: Keep only last 20 edits
        report.edited = report.edited[-20:]

    for err in errors:
        report.error.append(ErrorAction(
            timestamp=timestamp,
            tools_used=[err.get("tool", "unknown")],
            commands_executed=[],
            error_message=err.get("error", "Unknown error"),
            file_location="unknown",
            reason="Tool execution exception during ReAct loop.",
        ))
        
    # Sliding Window: Keep only last 20 errors
    report.error = report.error[-20:]

    return final_content or f"[{agent_name}] Task executed."


# ─────────────────────────────────────────────────────────────────────────────
# Tool resolver — get actual tool callables from agent node
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_tools(agent_name: str, root_node) -> list:
    """Find the AgentNode by common_name and return its tool list."""
    if root_node is None:
        return []

    node = root_node.find_neuron_by_name(agent_name)
    if node is None:
        return []

    if hasattr(node, "tools") and node.tools:
        return list(node.tools)

    # If tools not yet initialized, trigger initialize_agent
    try:
        node.initialize_agent()
        return list(node.tools) if hasattr(node, "tools") and node.tools else []
    except Exception as e:
        print_telemetry(f"  ⚠️ Could not resolve tools for {agent_name}: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# AgentFactory — Unfreeze phase shim (used by agent_node.initialize_agent)
# ─────────────────────────────────────────────────────────────────────────────

class AgentFactory:
    """
    Thin shim used by AgentNode.initialize_agent() during the UNFREEZE phase.

    Creates a LangGraph ReAct agent bound to a system prompt, model, and tools.
    This is NOT used during freeze execution — neural_agent() handles that.
    """

    @staticmethod
    def create_agent(
        system_prompt: str,
        model_name: str = None,
        tools: list = None,
    ):
        """
        Create and return a LangGraph create_react_agent instance.

        Args:
            system_prompt: The full system prompt for this agent.
            model_name:    Optional model override (uses LLMConnector default if None).
            tools:         List of LangChain tool callables.

        Returns:
            A compiled LangGraph agent ready for .invoke() calls.
        """
        from ..llm.connector import LLMConnector

        tools = tools or []
        llm = LLMConnector.get_llm(purpose="execution")
        checkpointer = MemorySaver()

        agent = create_react_agent(
            model=llm,
            tools=tools,
            checkpointer=checkpointer,
            prompt=system_prompt,
        )
        return agent

