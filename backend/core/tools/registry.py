"""
core/tools/registry.py
━━━━━━━━━━━━━━━━━━━━━━
LAYER  : Tools
ROLE   : Data-driven Tool Registry — maps agent_type → allowed tools via capability tags.

KEY CONCEPTS IN THIS FILE:
  • CAPABILITY_TAGS         (line ~30) — Named categories of functionality (file_read, shell_execution, etc.)
  • TOOL_REGISTRY           (line ~47) — Maps every tool name → which capability tags it provides
  • AGENT_CAPABILITY_MAP    (line ~89) — Maps every agent_type → which capability tags it is allowed to use
  • resolve_tools_for_agent (line ~139)— The resolver: filters the full tool pool to only allowed tools
  • get_tool_names_for_agent(line ~182)— Debug helper: returns tool names without instantiating objects

HOW TO ADD A NEW TOOL:
  1. Write the tool in the appropriate sub-package (e.g. core/tools/filesystem/).
  2. Add one line to TOOL_REGISTRY with its capability tags.
  3. Done — any agent_type that needs that capability gets it automatically.

HOW TO ADD A NEW AGENT TYPE:
  1. Add one line to AGENT_CAPABILITY_MAP with the required capability tags.
  2. Done — call set_agent_type("your_new_type") in your tree builder.

DEPENDS ON:
  • core/agents/agent_node.py — calls set_agent_type() which validates against this registry

CALLED BY:
  • core/agents/agent_node.py → initialize_agent() — resolves tool list at agent startup
"""


from __future__ import annotations
from typing import Any


# ── Capability Tags ───────────────────────────────────────────────────────────
# Each tag represents a category of functionality.
# Tools declare WHICH tags they provide.
# Agent types declare WHICH tags they need.

CAPABILITY_TAGS: dict[str, str] = {
    "file_read":         "Read files and directories in the sandbox",
    "file_write":        "Create and overwrite files in the sandbox",
    "shell_execution":   "Execute terminal/shell commands",
    "error_analysis":    "Query incident memory to suggest fixes for errors",
    "coordination":      "Read/write shared manifests and API contracts",
    "human_interaction": "Ask questions to the human user and collect answers",
    "document_parsing":  "Parse PDF, DOCX, and TXT documents",
    "web_search":        "Perform internet searches to find information",
    "styled_output":     "Generate beautifully styled HTML/CSS PDF documents and reports",
    "web_audit":         "Perform live browser visual layout, alignment, and console/network audits using Vision",
}


# ── Tool Registry ─────────────────────────────────────────────────────────────
# Maps tool name → list of capability tags it provides.
# Tool names MUST exactly match the `.name` attribute of the LangChain tool object.

TOOL_REGISTRY: dict[str, list[str]] = {
    # Filesystem — read
    "read_file":            ["file_read"],
    "list_directory":       ["file_read"],
    "search_codebase":      ["file_read"],
    "edit_file_patch":      ["file_read", "file_write"],  # needs read to locate, write to patch

    # Filesystem — write
    "write_file":           ["file_write"],
    "create_directory":     ["file_write"],

    # Coordination
    "list_manifest":        ["coordination"],
    "publish_contract":     ["coordination"],
    "read_contracts":       ["coordination"],

    # Execution
    "execute_command":      ["shell_execution"],
    "suggest_fix":          ["error_analysis"],

    # Human Handoff
    "ask_human":            ["human_interaction"],
    "ask_human_multi":      ["human_interaction"],
    "confirm_action":       ["human_interaction"],
    "send_whatsapp_web_message": ["human_interaction"],
    "whatsapp_user_chat":   ["human_interaction"],

    # Document Parsing & Generation
    "upload_document":      ["document_parsing"],
    "parse_pdf":            ["document_parsing"],
    "parse_docx":           ["document_parsing"],
    "parse_text_file":      ["document_parsing"],
    "generate_pdf_from_md":          ["document_parsing", "file_write"],
    "generate_styled_pdf_from_md":   ["styled_output", "file_write"],
    
    # Web Search
    "perform_web_search":   ["web_search"],

    # Web Audit
    "browser_vision_audit": ["web_audit"],
}

# ── Global Tool Object Pool ───────────────────────────────────────────────────
# Holds actual LangChain tool objects that have been registered.
_GLOBAL_TOOL_POOL: dict[str, Any] = {}

def register_tool(tool_func: Any, capabilities: list[str]) -> None:
    """
    Register a custom LangChain @tool with the framework.
    
    Args:
        tool_func: The actual tool function decorated with @tool.
        capabilities: A list of capability strings (e.g. ["sql_read"]).
    """
    tool_name = getattr(tool_func, "name", None)
    if not tool_name:
        raise ValueError("Provided tool_func must have a .name attribute (is it a LangChain @tool?)")
    
    TOOL_REGISTRY[tool_name] = capabilities
    _GLOBAL_TOOL_POOL[tool_name] = tool_func
    
    # Auto-register capabilities if they are new
    for cap in capabilities:
        if cap not in CAPABILITY_TAGS:
            CAPABILITY_TAGS[cap] = f"Custom capability: {cap}"


# ── Agent Capability Map ──────────────────────────────────────────────────────
# Maps agent_type → list of capability tags the agent is allowed to use.
# A tool is included if it provides ANY tag in the agent's allowed list.

AGENT_CAPABILITY_MAP: dict[str, list[str]] = {
    # ── Code / Build agent types ──────────────────────────────────────────────
    "writer": [
        "file_read",
        "file_write",
        "coordination",
        "document_parsing",
        "styled_output",
        "web_audit",
    ],
    "runner": [
        "file_read",
        "file_write",
        "shell_execution",
        "error_analysis",
        "coordination",
        "web_audit",
    ],
    "architect": [
        "file_read",
        "file_write",
        "shell_execution",
        "coordination",
        "web_audit",
    ],
    "assembler": [
        "file_read",
        "file_write",
        "coordination",
    ],

    # ── Conversational / HR agent types ───────────────────────────────────────
    "interviewer": [
        "human_interaction",
        "document_parsing",
        # no 'coordination' — HR agents don't need file manifests or contracts
    ],
    "chat": [
        "human_interaction",
        # no 'coordination' — router agents don't need file-system contracts
    ],

    # ── Research / Data agent types ───────────────────────────────────────────
    "researcher": [
        "file_read",
        "document_parsing",
        "coordination",
        "web_search",
    ],
    "analyst": [
        "file_read",
        "shell_execution",
        "coordination",
    ],
    "tester": [
        "file_read",
        "shell_execution",
        "coordination",
        "web_audit",
    ],
}

def register_agent_type(agent_type: str, capabilities: list[str]) -> None:
    """
    Register a custom agent type with a specific set of capability tags.
    
    Args:
        agent_type: The unique name of the agent type (e.g., "data_scientist").
        capabilities: A list of capability strings (e.g., ["sql_read", "shell_execution"]).
    """
    AGENT_CAPABILITY_MAP[agent_type] = capabilities


# ── Resolver ──────────────────────────────────────────────────────────────────

def resolve_tools_for_agent(agent_type: str, all_tool_objects: list) -> list:
    """
    Given an agent_type and a pool of available tool objects,
    return only the tools whose capability tags overlap with what
    this agent_type is allowed to use.

    Args:
        agent_type:       One of the keys in AGENT_CAPABILITY_MAP.
        all_tool_objects: A list of LangChain tool objects to filter.
                          (Legacy: now also merges with _GLOBAL_TOOL_POOL).

    Returns:
        A filtered list of tool objects appropriate for this agent type.
        >>> tools = resolve_tools_for_agent("interviewer", all_tools)
        # → [ask_human, ask_human_multi, confirm_action, upload_document, ...]
    """
    allowed_caps = AGENT_CAPABILITY_MAP.get(agent_type, ["file_read"])

    # Merge explicitly passed tools with dynamically registered global tools
    merged_pool = {getattr(t, "name"): t for t in all_tool_objects if getattr(t, "name", None)}
    merged_pool.update(_GLOBAL_TOOL_POOL)

    resolved = []
    for tool_name, tool_obj in merged_pool.items():
        tool_caps = TOOL_REGISTRY.get(tool_name, [])
        # If any of the tool's caps match the agent's allowed caps, it gets the tool.
        if any(cap in allowed_caps for cap in tool_caps):
            resolved.append(tool_obj)

    return resolved


def get_capabilities_for_type(agent_type: str) -> list[str]:
    """Returns the list of allowed capability tags for a given agent_type."""
    return AGENT_CAPABILITY_MAP.get(agent_type, ["file_read"])


def list_all_agent_types() -> list[str]:
    """Returns all registered agent types."""
    return list(AGENT_CAPABILITY_MAP.keys())


def get_tool_names_for_agent(agent_type: str) -> list[str]:
    """
    Returns the names of all tools assigned to a given agent_type based on
    its capability tags. Useful for visualization and debugging without
    instantiating the actual tool objects.
    """
    allowed_caps = get_capabilities_for_type(agent_type)
    tool_names = []
    for tool_name, tool_caps in TOOL_REGISTRY.items():
        if any(cap in allowed_caps for cap in tool_caps):
            tool_names.append(tool_name)
    return sorted(tool_names)
