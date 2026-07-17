"""
core/engine/prompt_builder.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unified system prompt assembler for LangNeurons agents.

Builds the 8-section system prompt from live state and injects into agent_prompt.md.
Section 8 (Decision Rules) is generated dynamically per agent:
  - Human-facing mode (supervisor=human): conversational, greet-first
  - Agent-facing mode (supervisor=agent): structured protocol, strict tool enforcement

Called by neural_agent() on every turn.
Also called by state_viewer.py to visualise the full prompt per agent.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from ..utils.prompt_loader import PromptLoader
from ..tools.registry import TOOL_REGISTRY, CAPABILITY_TAGS, AGENT_CAPABILITY_MAP


# ─────────────────────────────────────────────────────────────────────────────
# Tool description helpers
# ─────────────────────────────────────────────────────────────────────────────

_TOOL_DESCRIPTIONS: dict[str, dict] = {
    # Filesystem
    "read_file": {
        "description": "Read the contents of any file in the workspace.",
        "use_when": "You need to inspect existing code, config, or data before acting.",
    },
    "list_directory": {
        "description": "List files and folders inside a directory.",
        "use_when": "You need to understand the current project structure.",
    },
    "search_codebase": {
        "description": "Search for a pattern or keyword across all files.",
        "use_when": "You need to locate where something is defined or referenced.",
    },
    "write_file": {
        "description": "Create or overwrite a file with specified content.",
        "use_when": "You need to create a new source file or configuration file.",
    },
    "edit_file_patch": {
        "description": "Make targeted edits to an existing file using patch instructions.",
        "use_when": "You need to modify specific lines without rewriting the entire file.",
    },
    "create_directory": {
        "description": "Create a new directory (and any required parent directories).",
        "use_when": "You need to set up a folder structure before writing files.",
    },
    "list_manifest": {
        "description": "Read the shared team manifest of created files and contracts.",
        "use_when": "You want to know what files the team has already produced.",
    },
    # Coordination
    "publish_contract": {
        "description": "Publish an interface contract (API shape, schema) to the shared team ledger.",
        "use_when": "You have defined an interface that other agents need to implement against.",
    },
    "read_contracts": {
        "description": "Read all interface contracts published by the team.",
        "use_when": "You need to know the expected API shape before implementing.",
    },
    # Execution
    "execute_command": {
        "description": "Run a shell command (npm, python, pytest, docker, etc.) in the workspace.",
        "use_when": "You need to install dependencies, run tests, build, or start a service.",
    },
    "suggest_fix": {
        "description": "Query incident memory to get a fix suggestion for a specific error.",
        "use_when": "You hit an error and want to check if a similar error was resolved before.",
    },
    # Human handoff
    "ask_human": {
        "description": "Ask the human user a single question and wait for their answer.",
        "use_when": "You are missing a critical piece of information that only the user can provide.",
    },
    "ask_human_multi": {
        "description": "Ask the human user multiple questions in one interaction.",
        "use_when": "You need several pieces of information from the user before proceeding.",
    },
    "confirm_action": {
        "description": "Ask the human user to confirm before taking a significant action.",
        "use_when": "The next action is destructive, irreversible, or high-risk.",
    },
    # Document parsing
    "upload_document": {
        "description": "Accept a file upload from the user (PDF, DOCX, TXT).",
        "use_when": "The user wants to provide a document for you to process.",
    },
    "parse_pdf": {
        "description": "Extract structured text from a PDF document.",
        "use_when": "You received a PDF and need its text content.",
    },
    "parse_docx": {
        "description": "Extract structured text from a DOCX (Word) document.",
        "use_when": "You received a Word document and need its text content.",
    },
    "parse_text_file": {
        "description": "Read and return the text content of a plain text file.",
        "use_when": "You received a .txt file and need its contents.",
    },
}


def _build_tools_block(tool_names: list[str]) -> str:
    """Format tool list with descriptions and when-to-use guidance."""
    if not tool_names:
        return "None — you are a supervisor agent. Delegate tasks to your subordinates only."

    lines = []
    for name in sorted(set(tool_names)):
        meta = _TOOL_DESCRIPTIONS.get(name, {})
        description = meta.get("description", "General-purpose tool.")
        use_when = meta.get("use_when", "When this capability is required.")
        lines.append(
            f"  • {name}\n"
            f"      Description : {description}\n"
            f"      Use when    : {use_when}"
        )

    return "\n\n".join(lines) if lines else "None"


# ─────────────────────────────────────────────────────────────────────────────
# Supervisor block
# ─────────────────────────────────────────────────────────────────────────────

def _build_supervisor_block(agent_node) -> tuple[str, str]:
    """
    Returns (supervisor_block_text, supervisor_name).
    supervisor_name is used in the output schema placeholders.
    """
    if agent_node.parent is None:
        name = "human"
        block = (
            "  Supervisor  : human (the end user)\n"
            "  Persona     : The human user who initiated this session.\n"
            "  Instruction : Complete the task and return a clear, human-readable response."
        )
    else:
        p = agent_node.parent
        name = p.common_name
        role = p.dynamic_name or p.common_name
        # Try to pull a one-line persona hint from the parent's first skill
        persona_hint = ""
        if getattr(p, "skills", None):
            first_instr = p.skills[0].instructions.strip()
            persona_hint = first_instr.splitlines()[0][:120] if first_instr else ""

        block = (
            f"  Supervisor  : {name} ({role})\n"
            f"  Persona     : {persona_hint or 'Hierarchical supervisor — strategic and structured.'}\n"
            f"  Instruction : Complete your task fully, then return your response_provided to {name}. "
            f"Do not escalate past {name} unless explicitly told to."
        )
    return block, name


# ─────────────────────────────────────────────────────────────────────────────
# Subordinates block
# ─────────────────────────────────────────────────────────────────────────────

def _build_subordinates_block(agent_node) -> str:
    """Format subordinate list with capabilities and persona hint."""
    if not agent_node.children:
        return (
            "None — you are a leaf agent. Do NOT delegate.\n"
            "Use your tools to complete the task directly."
        )

    lines = []
    for child in agent_node.children:
        role = child.dynamic_name or child.common_name
        agent_type = getattr(child, "agent_type", "writer")

        # Capability tags from registry
        allowed_caps = AGENT_CAPABILITY_MAP.get(agent_type, [])
        cap_labels = [CAPABILITY_TAGS.get(c, c) for c in allowed_caps]
        caps_str = ", ".join(cap_labels) if cap_labels else "General execution"

        # Persona hint from first skill if available
        skill_hint = ""
        if getattr(child, "skills", None):
            raw = child.skills[0].instructions.strip()
            skill_hint = raw.splitlines()[0][:150] if raw else ""

        lines.append(
            f"  • {child.common_name}  ({role})\n"
            f"      Agent type   : {agent_type}\n"
            f"      Capabilities : {caps_str}\n"
            f"      Skill hint   : {skill_hint or 'See team directory for responsibilities.'}"
        )

    lines.append(
        "\n  DELEGATION RULE: Delegate sequentially. "
        "The first agent in your delegation_plan executes first. "
        "Wait for its full response before starting the next."
    )
    return "\n\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Tool report formatter  (accepts raw dict OR Pydantic AgentToolReport objects)
# ─────────────────────────────────────────────────────────────────────────────

def _format_completed_tasks(team_execution_report: dict) -> str:
    """
    Format completed task summaries from team_execution_report.
    Shows what each agent was asked to do and what they returned.
    This is the primary source of inter-agent state visibility.
    """
    if not team_execution_report:
        return ""

    lines = []
    for agent_name, record in team_execution_report.items():
        # Support both Pydantic objects and plain dicts
        def _get(obj, attr, default=""):
            if hasattr(obj, attr):
                return getattr(obj, attr)
            if isinstance(obj, dict):
                return obj.get(attr, default)
            return default

        task_received = _get(record, "task_received")
        if not task_received:
            continue

        response = _get(task_received, "response_provided", "")
        task_instr = _get(task_received, "task_instructions", "")

        # Only show completed tasks (skip pending/in_progress)
        if not response or response.lower() in ("pending", "in_progress", ""):
            continue

        short_task = task_instr[:80] + "..." if len(task_instr) > 80 else task_instr
        lines.append(
            f"  [{agent_name}]\n"
            f"    Task    : {short_task}\n"
            f"    Result  : {response}"
        )

        # Also include delegated sub-tasks if any
        tasks_delegated = _get(record, "tasks_delegated", [])
        for delegation in tasks_delegated:
            sub = _get(delegation, "subordinate_agent", "?")
            sub_resp = _get(delegation, "task_response", "")
            if sub_resp and sub_resp.lower() not in ("pending", ""):
                lines.append(f"    └─ [{sub}]: {sub_resp[:120]}")

    return "\n\n".join(lines) if lines else ""


def _format_tool_report(team_tool_report: dict, team_execution_report: dict | None = None) -> str:
    """
    Serialise the full team activity into Section 6.
    Includes:
      A) Completed task summaries (from team_execution_report) — highest priority
      B) Tool operations (from team_tool_report) — what tools were called
    """
    sections = []

    # Part A: Completed task summaries (most useful for inter-agent awareness)
    if team_execution_report:
        completed = _format_completed_tasks(team_execution_report)
        if completed:
            sections.append("── COMPLETED TASKS ──\n" + completed)

    if not team_tool_report:
        if not sections:
            return "(Empty — no activity yet. The team has just started.)"
        return "\n\n".join(sections)

    # Part B: Tool operations (file reads, writes, data gathered)
    tool_lines = []
    for agent_name, report in team_tool_report.items():
        agent_lines = []

        # Support both Pydantic objects and plain dicts (from Redis)
        def _get_list(obj, attr):
            if hasattr(obj, attr):
                return getattr(obj, attr)
            if isinstance(obj, dict):
                return obj.get(attr, [])
            return []

        for w in _get_list(report, "write"):
            files = _get_list(w, "files_written")
            for fw in files:
                path = fw.get("file_path") if isinstance(fw, dict) else getattr(fw, "file_path", "?")
                desc = fw.get("description") if isinstance(fw, dict) else getattr(fw, "description", "")
                agent_lines.append(f"    CREATED : {path} — {desc}")

        for e in _get_list(report, "edited"):
            files = _get_list(e, "files_edited")
            for fe in files:
                path = fe.get("file_path") if isinstance(fe, dict) else getattr(fe, "file_path", "?")
                desc = fe.get("edit_description") if isinstance(fe, dict) else getattr(fe, "edit_description", "")
                agent_lines.append(f"    EDITED  : {path} — {desc}")

        for r in _get_list(report, "read"):
            items = _get_list(r, "data_gathered")
            for item in items:
                agent_lines.append(f"    READ    : {item}")

        for err in _get_list(report, "error"):
            msg = err.get("error_message") if isinstance(err, dict) else getattr(err, "error_message", "?")
            loc = err.get("file_location") if isinstance(err, dict) else getattr(err, "file_location", "?")
            agent_lines.append(f"    ERROR   : {msg}  (in {loc})")

        if agent_lines:
            tool_lines.append(f"  [{agent_name}]")
            tool_lines.extend(agent_lines)

    if tool_lines:
        sections.append("── TOOL OPERATIONS ──\n" + "\n".join(tool_lines))

    return "\n\n".join(sections) if sections else "(No activity recorded yet.)"

# ─────────────────────────────────────────────────────────────────────────────
# Skill loader
# ─────────────────────────────────────────────────────────────────────────────

def _load_skill(agent_name: str, session_id: str = "default") -> str:
    """Load the system prompt from the saved .md skill file."""
    skills_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../skills/definitions'))
    session_dir = os.path.join(skills_dir, session_id)
    safe_name = agent_name.replace(" ", "_").replace("/", "").replace("\\", "")
    filepath = os.path.join(session_dir, f"{safe_name}.md")
    if not os.path.exists(filepath):
        return f"No specialized skill found for {agent_name} in session {session_id}."
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read().strip()


# ─────────────────────────────────────────────────────────────────────────────
# Decision rules builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_decision_rules(agent_node, supervisor_name: str, tool_names: list[str]) -> str:
    is_leaf = len(agent_node.children) == 0
    has_tools = len(tool_names) > 0
    sub_list = ", ".join([f"{c.common_name} ({c.dynamic_name or 'unassigned'})" for c in agent_node.children]) or "None"

    if supervisor_name == "human":
        return f"""YOUR THREE POSSIBLE ACTIONS:
  A. respond   → Return a conversational message directly to the human.
  B. delegate  → Send a task to one of your subordinates (listed in Section 4).
  C. use_tool  → Execute a tool directly (only if no subordinates can handle it).
                 CRITICAL: You only have human interaction tools (ask_human). You DO NOT have filesystem, search, or execution tools.
                 If the user asks to read files, inspect folders, run commands, or test code, you MUST choose 'delegate' to send this task to a subordinate who possesses these tools. NEVER choose 'use_tool' for filesystem or command execution tasks.

DECISION STEPS (in this exact order):

  STEP 1 — Check SECTION 7 (your history) FIRST.
    → Is your history EMPTY (no prior turns)?
        AND the message is a greeting (hi/hello/hey/ok/yes/sure)?
        → action = "respond". Introduce yourself warmly. Ask what they need. DO NOT delegate.

    → Is your history NON-EMPTY?
        → DO NOT re-introduce yourself. You have already greeted them.
        → "ok", "yes", "proceed", "sure", "go ahead" = user wants the NEXT STEP.
        → Read your history to determine which phase is complete, then proceed to the next.
        → Never say "Hello, I am the RouterAgent..." again if history is non-empty.

  STEP 2 — Determine your current workflow phase from Section 7 + Section 6.
    → What work has already been completed? (Check team tool report + your history)
    → What is the next incomplete phase?
    → Delegate to the appropriate subordinate for that phase.

  STEP 3 — Apply SECTION 1 (your skill & responsibilities).
    → Which subordinate handles the next step? ({sub_list})
    → Delegate SEQUENTIALLY. One agent at a time.
    → Pass ALL relevant context (candidate name, experience, skills, company) in the task.
    → If the task requires filesystem access (checking directories, reading files, running docker/commands), you MUST delegate. Do NOT try to run tools yourself as you only have human interaction tools.

  STEP 4 — After all delegations complete:
    → Generate a highly conversational, structured, and polite response for the human user.
    → STRUCTURE YOUR FINAL RESPONSE TO THE HUMAN PRECISELY AS FOLLOWS:
        1. Polite Greeting & Context: Warmly state what task you received and acknowledge the user.
        2. Natural Summary: Clearly outline what you and your team accomplished (what we did/produced) in elegant, human-like language. Avoid bulleted lists of dry logs; tell a story.
        3. Clear Consent Check: ALWAYS end your message by explicitly asking a natural, conversational question just like ChatGPT, such as: "Can we proceed with the next step?", "Would you like me to move on to the next phase?", or "Should I proceed with the next step?"
    → Never expose internal JSON, agent names, or technical state to the human.
    → Speak as if you are the single point of contact. Summarise the outcome naturally.

CRITICAL RULES:
  ✔ NEVER re-greet or re-introduce if history is non-empty.
  ✔ NEVER say "All delegated tasks completed. AgentName: {{raw_json}}" to the human.
  ✔ NEVER expose JSON, agent names, or internal workflow to the human.
  ✔ ALWAYS respond conversationally, warmly, and politely like a helpful human manager.
  ✔ ALWAYS close by asking: "Can we proceed with the next step?", "Would you like me to move on to the next phase?", or "Should I proceed with the next step?"
  ✔ SEQUENTIAL: Delegate one agent at a time. Never parallel.
  ✔ GREET FIRST: Only on very first turn (empty history) + greeting message."""

    else:
        # ── Agent-facing mode: all non-root agents ────────────────────────────
        tool_note = ""
        if is_leaf and has_tools:
            tool_note = (
                "\n  ⚠️  TOOL RULE: You are a leaf agent and you have tools. "
                "If you need external data, search the web, read files, or parse docs, use action='use_tool'. "
                "If you already know the answer and do NOT need any tools, you may use action='respond' directly using your own generated knowledge."
            )
        elif is_leaf and not has_tools:
            tool_note = "\n  ⚠️  You are a leaf agent with no tools. Use action='respond' with your analysis."

        return f"""COMMUNICATION MODE: AGENT-FACING (structured protocol)
Your supervisor is {supervisor_name} (an AI agent). Communicate with precision.

YOUR THREE POSSIBLE ACTIONS:
  A. use_tool  → Execute tools to complete the task.
  B. delegate  → Send task to a subordinate (only if you have subordinates).
  C. respond   → Return a final answer (only if no tools needed and task is purely analytical).{tool_note}

DECISION STEPS (in this exact order):

  STEP 1 — Check SECTION 7 (your history).
    → Have you already done this exact task? Return the prior result.
    → Is this a continuation? Use your history to pick up where you left off.

  STEP 2 — Check SECTION 6 (team tool report).
    → What data has already been gathered? Use it. Do not re-gather.
    → What files exist? Do not recreate them.

  STEP 3 — Apply SECTION 1 (your responsibilities).
    → Does this task require tools (SECTION 5)? → action = 'use_tool'
    → Does this task require a subordinate (SECTION 4)? → action = 'delegate'
    → Is the answer purely informational with no tool needed? → action = 'respond'

CRITICAL RULES:
  ✔ LEAF + TOOLS = MUST use_tool. Never skip tools if you have them.
  ✔ SEQUENTIAL: Delegate one subordinate at a time.
  ✔ BOUNDARY: Stay within your skill scope from SECTION 1.
  ✔ NO INVENTION: Never claim data unless SECTION 6 or SECTION 7 confirms it.
  ✔ NO FABRICATION: Never claim a subordinate responded until you receive their response.
  ✔ Your response_provided must be a plain text summary — never JSON."""

# ─────────────────────────────────────────────────────────────────────────────
# MAIN PUBLIC FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def build_agent_prompt(
    agent_node,
    session_id: str,
    current_task: str,
    supervisor_name: str,
    team_tool_report: dict,
    conversation_history: Optional[str] = None,
    tool_names: Optional[list[str]] = None,
    team_execution_report: Optional[dict] = None,
) -> str:
    """
    Assemble the complete unified 8-section system prompt for an agent.

    Section 8 (Decision Rules) is generated dynamically:
    - Human-facing mode when supervisor_name == "human"
    - Agent-facing mode for all other supervisors

    Args:
        agent_node:             The AgentNode instance (for tree traversal).
        session_id:             Redis session key (for skill file + history).
        current_task:           The task instructions this agent received.
        supervisor_name:        common_name of the agent who assigned the task.
        team_tool_report:       Dict from LangneuralState.team_tool_report (live state).
        conversation_history:   Pre-formatted string from load_agent_history() or None.
        tool_names:             List of tool names assigned to this agent.
        team_execution_report:  Dict from LangneuralState.team_execution_report — shows
                                what every agent was asked and what they returned.
                                Used to populate Section 6 with inter-agent awareness.

    Returns:
        Fully assembled system prompt string, ready to pass to LLM.
    """
    resolved_tool_names = tool_names or []

    # 1. Skill
    skill = _load_skill(agent_node.common_name, session_id)

    # 2. Team directory (built from live tree for freshness)
    from ..modules.skill_generator import SkillGenerator
    team_directory = SkillGenerator._build_team_directory(_get_tree_root(agent_node))

    # 3. Supervisor block
    supervisor_block, resolved_supervisor_name = _build_supervisor_block(agent_node)

    # 4. Subordinates block
    subordinates_block = _build_subordinates_block(agent_node)

    # 5. Tools block
    tools_block = _build_tools_block(resolved_tool_names)

    # 6. Team activity report (tool ops + completed task summaries)
    tool_report_text = _format_tool_report(team_tool_report, team_execution_report)

    # 7. Conversation history
    history_text = conversation_history or "(No prior history — this is your first task.)"

    # 8. Decision rules — mode-aware (human-facing vs agent-facing)
    decision_rules = _build_decision_rules(
        agent_node=agent_node,
        supervisor_name=resolved_supervisor_name,
        tool_names=resolved_tool_names,
    )

    # Render template
    prompt = PromptLoader.get_prompt(
        "system/agent_prompt.md",
        skill=skill,
        team_directory=team_directory,
        supervisor_block=supervisor_block,
        subordinates_block=subordinates_block,
        tools_block=tools_block,
        team_tool_report=tool_report_text,
        conversation_history=history_text,
        decision_rules=decision_rules,
    )

    return prompt


# ─────────────────────────────────────────────────────────────────────────────
# Helper — walk up to root
# ─────────────────────────────────────────────────────────────────────────────

def _get_tree_root(node):
    """Walk up the parent chain to find the root node."""
    current = node
    while current.parent is not None:
        current = current.parent
    return current
