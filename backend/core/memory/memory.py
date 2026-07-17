"""
Dual-state memory: private per-agent cognition + shared organizational timeline.

Production-grade Redis-backed implementation.

Private State (per-agent, invisible to others):
    - reasoning, planning, internal decisions, local memory
    - Redis key: private_state:{session_id}:{agent_id}

Shared State (visible to all authorized agents):
    - conversation timeline (user↔agent + agent↔agent)
    - active responsibilities board
    - agent metadata registry (structured outputs from completed tasks)
    - Redis keys:
        shared_timeline:{session_id}          → list of SharedEvent JSON
        shared_responsibilities:{session_id}  → hash of responsibility_id → JSON
        shared_metadata:{session_id}:{agent}  → list of ResponsibilityMetadata JSON
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ..engine.memory import RedisClient
from .contracts import Responsibility, ResponsibilityMetadata, SharedEvent

_redis_instance = RedisClient()
_redis = _redis_instance.get_client()


@dataclass
class PrivateStateStore:
    """
    Per-agent internal cognition store — only the owning agent reads/writes.

    Contains reasoning, temporary planning, intermediate decisions, self-evaluation.
    Acts like the agent's private brain.
    """

    session_id: str = "default"

    def _key(self, agent_id: str) -> str:
        return f"private_state:{self.session_id}:{agent_id}"

    def update(self, agent_id: str, values: dict[str, Any]) -> None:
        """Merge values into this agent's private state."""
        key = self._key(agent_id)
        current = self.get(agent_id)
        current.update(values)
        _redis.set(key, json.dumps(current))

    def get(self, agent_id: str) -> dict[str, Any]:
        """Return this agent's full private state dict."""
        raw = _redis.get(self._key(agent_id))
        if raw:
            return json.loads(raw.decode())
        return {}

    def clear(self, agent_id: str) -> None:
        """Wipe this agent's private state."""
        _redis.delete(self._key(agent_id))

    def clear_all(self) -> None:
        """Wipe all private state for this session."""
        for key in _redis.keys(f"private_state:{self.session_id}:*"):
            _redis.delete(key)


@dataclass
class SharedStateStore:
    """
    Organizational memory — visible to all authorized agents in the team.

    Contains:
        - Conversation timeline (user↔agent, agent↔agent, delegations, transitions)
        - Active responsibilities board (who is doing what, current status)
        - Agent metadata registry (structured outputs from completed tasks)

    Acts like the organization's shared workspace / team dashboard.
    """

    session_id: str = "default"
    max_events: int = 2000

    # ── Redis key helpers ─────────────────────────────────────────────────────

    @property
    def _timeline_key(self) -> str:
        return f"shared_timeline:{self.session_id}"

    @property
    def _responsibilities_key(self) -> str:
        return f"shared_responsibilities:{self.session_id}"

    def _metadata_key(self, agent: str) -> str:
        return f"shared_metadata:{self.session_id}:{agent}"

    # ── Timeline (append-only event log) ──────────────────────────────────────

    def append_event(self, event: SharedEvent) -> None:
        """Add an event to the shared timeline."""
        _redis.rpush(self._timeline_key, event.model_dump_json())
        # Trim to max_events
        length = _redis.llen(self._timeline_key)
        if length > self.max_events:
            _redis.ltrim(self._timeline_key, length - self.max_events, -1)

    def get_timeline(self, last_n: int = 50) -> list[SharedEvent]:
        """Return the most recent N events from the shared timeline."""
        if last_n <= 0:
            raw = _redis.lrange(self._timeline_key, 0, -1)
        else:
            raw = _redis.lrange(self._timeline_key, -last_n, -1)
        events = []
        for entry in raw:
            try:
                data = json.loads(entry.decode())
                events.append(SharedEvent(**data))
            except (json.JSONDecodeError, Exception):
                continue
        return events

    def format_timeline_for_prompt(self, last_n: int = 50) -> str:
        """
        Format the timeline as a readable string for injection into agent prompts.

        Example:
            [user → RouterAgent]: Hi there!
            [RouterAgent → IntroAgent] DELEGATE: Collect candidate info
            [IntroAgent → user]: Hello! What's your name?
        """
        events = self.get_timeline(last_n=last_n)
        if not events:
            return "(No organizational activity yet)"

        lines = []
        for event in events:
            sender = event.sender
            receiver = event.receiver or ""
            etype = event.event_type.value

            if etype == "user_message":
                lines.append(f"[{sender}]: {event.payload.get('content', '')}")
            elif etype == "agent_message":
                lines.append(f"[{sender}]: {event.payload.get('content', '')}")
            elif etype == "delegation":
                task = event.payload.get("task", "")
                lines.append(f"[{sender} → {receiver}] DELEGATE: {task}")
            elif etype == "transition":
                to_status = event.payload.get("to_status", "")
                title = event.payload.get("title", "")
                lines.append(f"[{sender}] STATUS: {title} → {to_status}")
            elif etype == "validation":
                passed = event.payload.get("passed", False)
                lines.append(f"[{sender}] VALIDATION: {'✅ PASSED' if passed else '❌ FAILED'}")
            elif etype == "metadata":
                lines.append(f"[{sender}] METADATA RECORDED")
            else:
                lines.append(f"[{sender}] {etype}: {json.dumps(event.payload)[:80]}")

        return "\n".join(lines)

    # ── Active Responsibilities Board ─────────────────────────────────────────

    def upsert_responsibility(self, responsibility: Responsibility) -> None:
        """Add or update a responsibility on the active board."""
        _redis.hset(
            self._responsibilities_key,
            responsibility.responsibility_id,
            responsibility.model_dump_json(),
        )

    def remove_responsibility(self, responsibility_id: str) -> None:
        """Remove a completed/cancelled responsibility from the active board."""
        _redis.hdel(self._responsibilities_key, responsibility_id)

    def get_responsibility(self, responsibility_id: str) -> Responsibility | None:
        """Get a specific responsibility by ID."""
        raw = _redis.hget(self._responsibilities_key, responsibility_id)
        if raw:
            return Responsibility(**json.loads(raw.decode()))
        return None

    def active_responsibilities_map(self) -> dict[str, dict[str, str]]:
        """
        Return a summary of all active responsibilities, keyed by owner agent.

        Example:
            {
                "FrontendDeveloper": {
                    "responsibility_id": "resp-1",
                    "current_task": "Build landing page",
                    "status": "in_progress"
                }
            }
        """
        all_raw = _redis.hgetall(self._responsibilities_key)
        result = {}
        for _rid, raw_data in all_raw.items():
            try:
                resp = Responsibility(**json.loads(raw_data.decode()))
                result[resp.owner_agent] = {
                    "responsibility_id": resp.responsibility_id,
                    "current_task": resp.title,
                    "status": resp.status.value,
                    "priority": resp.priority,
                }
            except (json.JSONDecodeError, Exception):
                continue
        return result

    def format_responsibilities_for_prompt(self) -> str:
        """Format active responsibilities as a readable block for agent prompts."""
        board = self.active_responsibilities_map()
        if not board:
            return "(No active responsibilities)"
        lines = []
        for agent, info in board.items():
            lines.append(
                f"  {agent}: {info['current_task']} [{info['status']}] "
                f"(priority: {info['priority']})"
            )
        return "\n".join(lines)

    # ── Agent Metadata Registry ───────────────────────────────────────────────

    def record_metadata(self, metadata: ResponsibilityMetadata) -> None:
        """
        Store structured output from a completed responsibility.
        This becomes organizational knowledge — other agents can query it.
        """
        key = self._metadata_key(metadata.agent)
        _redis.rpush(key, metadata.model_dump_json())
        # Keep last 20 metadata entries per agent
        _redis.ltrim(key, -20, -1)

    def get_agent_metadata(self, agent: str) -> list[ResponsibilityMetadata]:
        """Get all stored metadata for a specific agent."""
        key = self._metadata_key(agent)
        raw = _redis.lrange(key, 0, -1)
        result = []
        for entry in raw:
            try:
                data = json.loads(entry.decode())
                result.append(ResponsibilityMetadata(**data))
            except (json.JSONDecodeError, Exception):
                continue
        return result

    def metadata_registry(self) -> dict[str, list[ResponsibilityMetadata]]:
        """Return all agent metadata across the session."""
        result: dict[str, list[ResponsibilityMetadata]] = defaultdict(list)
        pattern = f"shared_metadata:{self.session_id}:*"
        for key in _redis.keys(pattern):
            agent = key.decode().split(":")[-1]
            result[agent] = self.get_agent_metadata(agent)
        return dict(result)

    def format_metadata_for_prompt(self) -> str:
        """Format all agent metadata as a readable block for prompt injection."""
        registry = self.metadata_registry()
        if not registry:
            return "(No agent metadata recorded yet)"
        lines = []
        for agent, entries in registry.items():
            if entries:
                latest = entries[-1]
                lines.append(
                    f"  {agent}: {latest.final_summary} "
                    f"[{latest.responsibility_status.value}]"
                )
        return "\n".join(lines)

    # ── Family Dashboard ──────────────────────────────────────────────────────
    # Tracks what each agent's direct subordinates have completed.
    # Key: family_dashboard:{session_id}:{parent_agent}
    # Value: JSON list of child completion entries (appended after each child finishes)

    def _family_key(self, parent_agent: str) -> str:
        return f"family_dashboard:{self.session_id}:{parent_agent}"

    def record_child_completion(self, parent_agent: str, child_entry: dict) -> None:
        """
        Append a child agent's completion record to the parent's family dashboard.

        Called after EVERY child finishes in the sequential delegation loop.
        The next sibling in the loop will see this entry in its context packet.

        child_entry keys (all domain-agnostic):
            child_name          — common_name of the child
            child_role          — dynamic_name / role of the child
            task                — the task that was delegated to the child
            status              — 'completed' | 'failed'
            deliverables        — list of items the child produced
            contracts_published — list of contract names the child published
            summary             — short free-text summary
            completed_at        — ISO timestamp
        """
        key = self._family_key(parent_agent)
        raw = _redis.get(key)
        dashboard = json.loads(raw.decode()) if raw else []
        dashboard.append(child_entry)
        _redis.set(key, json.dumps(dashboard))

    def get_family_dashboard(self, parent_agent: str) -> list:
        """Return the family dashboard for a given parent agent."""
        key = self._family_key(parent_agent)
        raw = _redis.get(key)
        if raw:
            try:
                return json.loads(raw.decode())
            except Exception:
                return []
        return []

    def clear_family_dashboard(self, parent_agent: str) -> None:
        """Wipe the family dashboard for a given parent agent."""
        _redis.delete(self._family_key(parent_agent))

    # ── Management ────────────────────────────────────────────────────────────

    def clear(self) -> None:
        """Wipe all shared state for this session (called on --clear-mem)."""
        _redis.delete(self._timeline_key)
        _redis.delete(self._responsibilities_key)
        for key in _redis.keys(f"shared_metadata:{self.session_id}:*"):
            _redis.delete(key)
        for key in _redis.keys(f"family_dashboard:{self.session_id}:*"):
            _redis.delete(key)
        # Also wipe Shared Engineering Intelligence for this session
        _redis.delete(f"sei:{self.session_id}")

    def timeline_length(self) -> int:
        """Return the number of events in the timeline."""
        return _redis.llen(self._timeline_key)
