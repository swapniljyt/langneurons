"""
core/tools/filesystem/directory.py
────────────────────────────────────
Directory creation and listing tools.
"""

import os
from langchain_core.tools import tool
from .read_write import _get_sandboxed_path, SANDBOX_DIR


@tool
def create_directory(dirpath: str) -> str:
    """
    create_directory(dirpath: str) -> str
    
    Creates a new directory (and any necessary parent directories) inside the sandbox.
    
    IMPORTANT RULES FOR USING THIS TOOL:
    1. Use this to safely scaffold folders before writing files to them.
    2. The dirpath must be relative to the sandbox root.
    3. Do NOT use this tool if you are just writing a file, because write_file automatically creates parent directories.

    Args:
        dirpath (str): The relative path of the directory to create (e.g., 'interview/data/output').
        
    Returns:
        str: Success or error message.
    """
    try:
        target_path = _get_sandboxed_path(dirpath)
        os.makedirs(target_path, exist_ok=True)
        return f"✅ Successfully created directory: sandbox/{os.path.relpath(target_path, SANDBOX_DIR)}"
    except Exception as e:
        return f"❌ Error creating directory: {str(e)}"


@tool
def list_directory(dirpath: str = ".") -> str:
    """
    list_directory(dirpath: str = ".") -> str
    
    Lists all files and subdirectories in the specified sandbox directory.
    
    IMPORTANT RULES FOR USING THIS TOOL:
    1. Use this to look around your namespace, verify what files exist, and avoid overwriting existing work.
    2. Pass "." to list the root of the sandbox.
    3. The dirpath must be relative to the sandbox root.

    Args:
        dirpath (str): The relative path to list. Defaults to the root of the sandbox (".").
        
    Returns:
        str: A formatted list of files and folders in the directory.
    """
    try:
        target_path = _get_sandboxed_path(dirpath)
        if not os.path.exists(target_path):
            return f"❌ Directory does not exist: {dirpath}"
        if not os.path.isdir(target_path):
            return f"❌ Path is not a directory: {dirpath}"

        items = os.listdir(target_path)
        if not items:
            return f"📂 Directory sandbox/{os.path.relpath(target_path, SANDBOX_DIR)} is empty."

        formatted_items = []
        for item in sorted(items):
            full_item_path = os.path.join(target_path, item)
            if os.path.isdir(full_item_path):
                formatted_items.append(f"📁 {item}/")
            else:
                formatted_items.append(f"📄 {item}")

        return f"Contents of sandbox/{os.path.relpath(target_path, SANDBOX_DIR)}:\n" + "\n".join(formatted_items)
    except Exception as e:
        return f"❌ Error listing directory: {str(e)}"
