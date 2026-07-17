"""
core/tools/filesystem/search.py
─────────────────────────────────
Codebase search and surgical file-patching tools.
"""

import os
import glob
import difflib
from langchain_core.tools import tool
from .read_write import _get_sandboxed_path, SANDBOX_DIR


@tool
def search_codebase(query: str, file_pattern: str = "**/*.*") -> str:
    """
    Searches the entire sandbox codebase for a specific string.
    Use this to find API routes, class definitions, or variable names written by other agents.
    This is essential for cross-team integration — always search before wiring teams together.

    Args:
        query:        The exact text string to search for (e.g., 'class User', '/api/v1/chat').
        file_pattern: Optional glob pattern to restrict search (e.g., 'apps/backend/**/*.py').
    """
    try:
        search_pattern = os.path.join(SANDBOX_DIR, file_pattern)
        matched_files  = glob.glob(search_pattern, recursive=True)
        results = []

        for filepath in matched_files:
            if not os.path.isfile(filepath):
                continue
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for i, line in enumerate(lines):
                        if query in line:
                            rel_path = os.path.relpath(filepath, SANDBOX_DIR)
                            results.append(f"Match in {rel_path} (Line {i+1}): {line.strip()}")
            except UnicodeDecodeError:
                pass

        if not results:
            return f"No matches found for '{query}' in pattern '{file_pattern}'."
        if len(results) > 50:
            return "\n".join(results[:50]) + f"\n... and {len(results)-50} more matches."
        return "\n".join(results)
    except Exception as e:
        return f"❌ Error searching codebase: {str(e)}"


@tool
def edit_file_patch(filepath: str, search_string: str, replace_string: str) -> str:
    """
    Surgically edits an existing file by replacing a specific string.
    Use this to modify files without rewriting the entire file content.
    This is far more efficient and safe than calling write_file on a large existing file.
    After patching, a colored diff is printed to the terminal showing exactly what changed.

    Args:
        filepath:      The relative path to the file inside the sandbox.
        search_string: The exact string to find in the file.
        replace_string: The string to replace it with.
    """
    RED   = "\033[31m"
    GREEN = "\033[32m"
    CYAN  = "\033[36m"
    DIM   = "\033[2m"
    BOLD  = "\033[1m"
    RESET = "\033[0m"

    try:
        target_path = _get_sandboxed_path(filepath)
        if not os.path.exists(target_path):
            return f"❌ File does not exist: {filepath}"

        with open(target_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        if search_string not in original_content:
            return (
                f"❌ Could not find the exact search string in {filepath}.\n"
                f"Searched for: {repr(search_string[:80])}"
            )

        new_content = original_content.replace(search_string, replace_string, 1)

        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        rel_path       = os.path.relpath(target_path, SANDBOX_DIR)
        original_lines = original_content.splitlines(keepends=True)
        new_lines      = new_content.splitlines(keepends=True)
        diff = list(difflib.unified_diff(
            original_lines, new_lines,
            fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}", lineterm=""
        ))

        print(f"\n{BOLD}────────────────── 📝 PATCH APPLIED: {rel_path} ──────────────────{RESET}")
        for line in diff:
            if line.startswith("---") or line.startswith("+++"):
                print(f"{BOLD}{CYAN}{line}{RESET}")
            elif line.startswith("@@"):
                print(f"{DIM}{line}{RESET}")
            elif line.startswith("-"):
                print(f"{RED}{line}{RESET}")
            elif line.startswith("+"):
                print(f"{GREEN}{line}{RESET}")
            else:
                print(f"{DIM}{line}{RESET}")
        print(f"{BOLD}────────────────────────────────────────────────────────────────{RESET}\n")

        return f"✅ Patched sandbox/{rel_path}  ({len(diff)} diff lines)"
    except Exception as e:
        return f"❌ Error patching file: {str(e)}"
