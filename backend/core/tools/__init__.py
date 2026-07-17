"""
core/tools/__init__.py
───────────────────────
Central re-export point for all LangNeurons tools.

Organized into sub-packages by responsibility:

  filesystem/   — read_file, write_file, create_directory, list_directory,
                  search_codebase, edit_file_patch, list_manifest,
                  create_namespaced_tools
  coordination/ — publish_contract, read_contracts
  execution/    — execute_command, create_runner_tools
  intelligence/ — create_sei_tools   (root_neuron only)
  handoff/      — ask_human, ask_human_multi, confirm_action
  documents/    — upload_document, parse_pdf, parse_docx, parse_text_file
  registry      — resolve_tools_for_agent, AGENT_CAPABILITY_MAP, TOOL_REGISTRY

Backward-compatibility aliases are provided so existing imports like
  from core.tools.filesystem import write_file, read_file
  from core.tools.intelligence_tools import create_sei_tools
  from core.tools.incident_tools import create_runner_tools
continue to work without modification.
"""

# ── Filesystem ────────────────────────────────────────────────────────────────
from .filesystem.read_write  import write_file, read_file, _get_sandboxed_path, _enforce_namespace, SANDBOX_DIR, MANIFEST_PATH
from .filesystem.directory   import create_directory, list_directory
from .filesystem.search      import search_codebase, edit_file_patch
from .filesystem.manifest    import list_manifest, _register_in_manifest
from .filesystem.namespaced  import create_namespaced_tools

# ── Coordination ──────────────────────────────────────────────────────────────
from .coordination.contracts import publish_contract, read_contracts

# ── Execution ─────────────────────────────────────────────────────────────────
from .execution.runner       import execute_command, create_runner_tools
from .execution.browser_audit import browser_vision_audit
from .execution.whatsapp     import send_whatsapp_web_message, whatsapp_user_chat

# ── Intelligence (root agent only) ────────────────────────────────────────────
from .intelligence.sei_tools import create_sei_tools

# ── Human Handoff ─────────────────────────────────────────────────────────────
from .handoff.human_tools    import ask_human, ask_human_multi, confirm_action

# ── Document Parsing ──────────────────────────────────────────────────────────
from .documents.parser_tools import upload_document, parse_pdf, parse_docx, parse_text_file

# ── Registry ──────────────────────────────────────────────────────────────────
from .registry import resolve_tools_for_agent, AGENT_CAPABILITY_MAP, TOOL_REGISTRY

__all__ = [
    # Filesystem
    "write_file", "read_file", "create_directory", "list_directory",
    "search_codebase", "edit_file_patch", "list_manifest", "create_namespaced_tools",
    # Coordination
    "publish_contract", "read_contracts",
    # Execution
    "execute_command", "create_runner_tools", "browser_vision_audit", "send_whatsapp_web_message", "whatsapp_user_chat",
    # Intelligence
    "create_sei_tools",
    # Handoff
    "ask_human", "ask_human_multi", "confirm_action",
    # Documents
    "upload_document", "parse_pdf", "parse_docx", "parse_text_file",
    # Registry
    "resolve_tools_for_agent", "AGENT_CAPABILITY_MAP", "TOOL_REGISTRY",
]
