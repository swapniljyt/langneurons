"""
core/tools/filesystem/namespaced.py
──────────────────────────────────────
Namespace-locked tool factory.

Creates hard-locked versions of write_file and create_directory for
Writer and Assembler agents so they literally cannot write outside their
assigned sandbox sub-directory.
"""

import os
from langchain_core.tools import StructuredTool
from pydantic import BaseModel
from .read_write import _get_sandboxed_path, _enforce_namespace, SANDBOX_DIR
from .manifest import _register_in_manifest


def create_namespaced_tools(namespace: str, agent_name: str = "unknown") -> list:
    """
    Factory: creates namespace-locked write_file and create_directory tools
    for a specific agent. Every write attempt that falls outside the assigned
    namespace is hard-rejected with a clear error message.

    Args:
        namespace:  The directory the agent is locked to (e.g., 'pages/api/').
        agent_name: The agent's display name — used in the manifest.

    Returns:
        List of [namespaced_write_file, namespaced_create_directory]
    """

    class WriteFileInput(BaseModel):
        filepath: str
        content:  str

    def _namespaced_write_file(filepath: str, content: str) -> str:
        try:
            target_path = _get_sandboxed_path(filepath)
            _enforce_namespace(target_path, namespace)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            # Auto-fix double-escaped newlines from LLM JSON serialization
            if '\\n' in content and '\n' not in content:
                try:
                    content = content.encode('raw_unicode_escape').decode('unicode_escape')
                except Exception:
                    pass

            from .read_write import intercept_file_write
            # Streams content to disk with live progress bar — no double write needed
            intercept_file_write(filepath, content, agent_name)
            _register_in_manifest(filepath, agent_name)
            rel = os.path.relpath(target_path, SANDBOX_DIR)
            return f"✅ [{agent_name}] Wrote to sandbox/{rel}"
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"❌ Error writing file: {str(e)}"

    class CreateDirInput(BaseModel):
        dirpath: str

    def _namespaced_create_directory(dirpath: str) -> str:
        try:
            target_path = _get_sandboxed_path(dirpath)
            _enforce_namespace(target_path, namespace)
            os.makedirs(target_path, exist_ok=True)
            rel = os.path.relpath(target_path, SANDBOX_DIR)
            return f"✅ [{agent_name}] Created directory sandbox/{rel}"
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"❌ Error creating directory: {str(e)}"

    namespaced_write = StructuredTool.from_function(
        func=_namespaced_write_file,
        name="write_file",
        description=(
            f"Writes a file. You are RESTRICTED to the `{namespace}` namespace. "
            f"Any attempt to write outside this directory will be hard-rejected. "
            f"Filepath must start with '{namespace}'."
        ),
        args_schema=WriteFileInput,
    )

    namespaced_create_dir = StructuredTool.from_function(
        func=_namespaced_create_directory,
        name="create_directory",
        description=(
            f"Creates a directory. You are RESTRICTED to the `{namespace}` namespace. "
            f"Dirpath must start with '{namespace}'."
        ),
        args_schema=CreateDirInput,
    )

    return [namespaced_write, namespaced_create_dir]
