"""
core/tools/filesystem/manifest.py
───────────────────────────────────
Shared file manifest — the global team whiteboard that tracks
which file was written by which agent during a session.
"""

import os
import json
from langchain_core.tools import tool
from .read_write import SANDBOX_DIR, MANIFEST_PATH


@tool
def list_manifest() -> str:
    """
    Lists ALL files created by ALL agents in this session.
    Use this FIRST before writing any code to understand what other teams have built.
    This is the team whiteboard — it shows who created what and where.
    """
    try:
        if not os.path.exists(MANIFEST_PATH):
            return "📋 File manifest is empty. No files have been written yet."
        with open(MANIFEST_PATH, 'r') as f:
            manifest = json.load(f)
        if not manifest:
            return "📋 File manifest is empty. No files have been written yet."
        lines = ["📋 SHARED FILE MANIFEST (All files created by the team):"]
        for path, info in sorted(manifest.items()):
            agent = info.get("written_by", "unknown")
            lines.append(f"  📄 {path}  [by: {agent}]")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error reading manifest: {str(e)}"


def _register_in_manifest(filepath: str, agent_name: str) -> None:
    """
    Internal helper: auto-registers a written file in the shared file manifest.
    Called directly from write_file and the namespaced tool factory.
    Not exposed as a LangChain tool.
    """
    try:
        manifest = {}
        if os.path.exists(MANIFEST_PATH):
            with open(MANIFEST_PATH, 'r') as f:
                manifest = json.load(f)
        clean = filepath.lstrip('/')
        if clean.startswith('sandbox/'):
            clean = clean[len('sandbox/'):]
        manifest[clean] = {"written_by": agent_name, "path": clean}
        with open(MANIFEST_PATH, 'w') as f:
            json.dump(manifest, f, indent=2)
    except Exception:
        pass
