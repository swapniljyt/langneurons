"""
core/tools/filesystem
─────────────────────
All file-system tools available to agents.

Public exports:
  write_file            — write a file to sandbox (unrestricted)
  read_file             — read a file from sandbox
  create_directory      — create a directory in sandbox
  list_directory        — list contents of a sandbox directory
  search_codebase       — keyword search across sandbox files
  edit_file_patch       — surgically replace a string in an existing file
  list_manifest         — read the global file manifest
  create_namespaced_tools — factory: returns namespace-locked write_file + create_directory
"""

from .read_write import write_file, read_file, _get_sandboxed_path, _enforce_namespace, SANDBOX_DIR, MANIFEST_PATH
from .directory import create_directory, list_directory
from .search import search_codebase, edit_file_patch
from .manifest import list_manifest, _register_in_manifest
from .namespaced import create_namespaced_tools

__all__ = [
    "write_file",
    "read_file",
    "create_directory",
    "list_directory",
    "search_codebase",
    "edit_file_patch",
    "list_manifest",
    "create_namespaced_tools",
    # internals needed by other sub-packages
    "_get_sandboxed_path",
    "_enforce_namespace",
    "_register_in_manifest",
    "SANDBOX_DIR",
    "MANIFEST_PATH",
]
