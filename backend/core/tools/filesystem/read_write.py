"""
core/tools/filesystem/read_write.py
─────────────────────────────────────
Core file read/write tools + sandbox path enforcement.
"""

import os
import json
import difflib
from langchain_core.tools import tool
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

# ── Sandbox root ──────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SANDBOX_DIR = os.path.join(BASE_DIR, "sandbox")
MANIFEST_PATH = os.path.join(SANDBOX_DIR, ".file_manifest.json")
os.makedirs(SANDBOX_DIR, exist_ok=True)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_sandboxed_path(filepath: str) -> str:
    """
    Ensures the filepath stays within the sandbox directory.
    Prevents double-nesting (e.g., sandbox/sandbox/) by stripping any
    leading 'sandbox/' from the input path.
    """
    clean_path = filepath.strip()
    while clean_path.startswith(('./', '/')):
        if clean_path.startswith('./'):
            clean_path = clean_path[2:]
        elif clean_path.startswith('/'):
            clean_path = clean_path[1:]
            
    if clean_path.startswith('sandbox/') or clean_path == 'sandbox':
        clean_path = clean_path[len('sandbox/'):]
        
    while clean_path.startswith(('./', '/')):
        if clean_path.startswith('./'):
            clean_path = clean_path[2:]
        elif clean_path.startswith('/'):
            clean_path = clean_path[1:]
            
    target_path = os.path.abspath(os.path.join(SANDBOX_DIR, clean_path))
    if not target_path.startswith(SANDBOX_DIR):
        raise ValueError(f"Access denied: Cannot access paths outside the sandbox ({filepath})")
    return target_path


def _enforce_namespace(target_path: str, namespace: str) -> None:
    """
    Hard namespace enforcement. Raises ValueError if target_path is
    outside the agent's assigned namespace.

    If the namespace looks like a FILE (last component has an extension,
    e.g. 'pages/index.js'), the PARENT DIRECTORY is used as the effective
    namespace boundary. This lets Assemblers create sibling files freely
    while still being locked to their one directory.
    """
    if not namespace:
        return

    ns_internal = namespace.lstrip('/')
    if ns_internal.startswith('sandbox/'):
        ns_internal = ns_internal[len('sandbox/'):]

    _, ns_ext = os.path.splitext(os.path.basename(ns_internal))
    if ns_ext:
        ns_internal = os.path.dirname(ns_internal)

    namespace_path = os.path.abspath(os.path.join(SANDBOX_DIR, ns_internal))

    if not (target_path + os.sep).startswith(namespace_path + os.sep):
        rel_target = os.path.relpath(target_path, SANDBOX_DIR)
        rel_ns     = os.path.relpath(namespace_path, SANDBOX_DIR)
        raise ValueError(
            f"🚫 NAMESPACE VIOLATION: You are restricted to `{rel_ns}/`. "
            f"Attempted to write to `{rel_target}`. "
            f"You MUST only write files within your assigned namespace."
        )


def intercept_file_write(filepath: str, content: str, agent_name: str) -> str:
    """
    Auto-approves all file writes (no human confirmation required).

    If _StreamingFileWriter already live-streamed this file during LLM generation,
    we do a silent final sync write (no animation needed — the user already saw it
    appear token-by-token in their editor).

    Otherwise: streams content token-by-token with a Rich progress bar.
    """
    from rich.console import Console
    console = Console()
    target_path = _get_sandboxed_path(filepath)

    # \u2500\u2500 Fast path: file was already live-streamed by _StreamingFileWriter \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    try:
        from core.engine.agent_factory import _already_streamed_paths
        if target_path in _already_streamed_paths:
            _already_streamed_paths.discard(target_path)   # consume the flag
            rel = os.path.relpath(target_path, SANDBOX_DIR)
            # Final sync: overwrite with complete content to fix any edge-case
            # JSON-decode errors that may have crept in during streaming.
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            console.print(
                f"[bold green]\u2714\ufe0f  [{agent_name}] sandbox/{rel} \u2014 "
                f"already live-streamed. Final sync done.[/bold green]"
            )
            return content
    except ImportError:
        pass   # agent_factory not available in this context \u2014 fall through
    import re
    import time
    from rich.syntax import Syntax
    from rich.panel import Panel
    from rich.live import Live

    rel = os.path.relpath(target_path, SANDBOX_DIR)

    # Detect syntax lexer from file extension
    lexer = (
        "html"       if filepath.endswith(".html") else
        "css"        if filepath.endswith(".css")  else
        "javascript" if filepath.endswith(".js")   else
        "python"     if filepath.endswith(".py")   else
        "text"
    )

    # Skip identical files silently
    if os.path.exists(target_path):
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                if f.read() == content:
                    console.print(
                        f"[yellow]⚠️  sandbox/{rel} — content unchanged, skipping.[/yellow]"
                    )
                    return content
        except Exception:
            pass

    total_chars  = len(content)
    total_lines  = content.count("\n") + 1

    console.print(
        f"\n[bold green]🚀 [{agent_name}] Streaming sandbox/{rel} "
        f"({total_lines} lines | {total_chars} chars)...[/bold green]"
    )

    # Split into LLM-style tokens: alternating words and whitespace/newlines
    tokens = re.findall(r'\S+|\s+', content)
    total_tokens = len(tokens)

    # Throttle: how many tokens between display refreshes
    # For large files refresh every ~10 tokens; small files every token
    refresh_every = max(1, total_tokens // 500)

    # Scroll window: how many lines to show in the live preview
    SCROLL_LINES = 18

    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    # Tiny per-token delay — adapts so large files don't take forever
    # Target: ~6-10 seconds total streaming time
    TARGET_SECS = min(8.0, max(3.0, total_tokens * 0.001))
    delay = TARGET_SECS / max(1, total_tokens)

    chars_written = 0
    buffer: list[str] = []          # rolling list of chars written so far

    with open(target_path, 'w', encoding='utf-8') as fh, \
         Live(auto_refresh=False, console=console) as live:

        for idx, token in enumerate(tokens, start=1):
            # ── Write token to disk immediately ───────────────────────────
            fh.write(token)
            fh.flush()
            chars_written += len(token)
            buffer.append(token)

            # ── Throttled terminal refresh ─────────────────────────────────
            if idx % refresh_every == 0 or idx == total_tokens:
                current_text  = "".join(buffer)
                current_lines = current_text.split("\n")
                start_line    = max(0, len(current_lines) - SCROLL_LINES)
                display_text  = "\n".join(current_lines[start_line:])

                percent = int((chars_written / total_chars) * 100)
                filled  = percent // 5
                bar     = "█" * filled + "░" * (20 - filled)

                panel_content = Syntax(
                    display_text, lexer, theme="monokai",
                    line_numbers=True, start_line=start_line + 1
                )
                live.update(
                    Panel(
                        panel_content,
                        title=(
                            f"[bold green]⌨  {agent_name} → sandbox/{rel}  "
                            f"token {idx}/{total_tokens}[/bold green]"
                        ),
                        subtitle=(
                            f"[bold yellow][{bar}] {percent}%  "
                            f"({chars_written}/{total_chars} chars)[/bold yellow]"
                        ),
                        border_style="green",
                    ),
                    refresh=True,
                )

            time.sleep(delay)

    console.print(f"[bold green]✅ sandbox/{rel} written successfully![/bold green]\n")
    return content


# ── Public tools ──────────────────────────────────────────────────────────────

@tool
def write_file(filepath: str, content: str) -> str:
    """
    write_file(filepath: str, content: str) -> str
    
    Creates or overwrites a file in the sandbox with the given text content.
    
    IMPORTANT RULES FOR USING THIS TOOL:
    1. Provide the FULL content you want to write. This tool OVERWRITES the file completely. It does NOT append.
    2. The filepath is relative to the sandbox root (e.g., 'interview/data/resume.txt').
    3. Use this tool when you need to save data, generate code, write reports, or store JSON configurations.
    4. If writing JSON, ensure it is properly formatted as a string.

    Args:
        filepath (str): The relative path to the file inside the sandbox (e.g., 'data/output.json').
        content (str): The complete raw text or JSON content to write into the file.
    """
    try:
        target_path = _get_sandboxed_path(filepath)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        rel = os.path.relpath(target_path, SANDBOX_DIR)

        # Auto-fix double-escaped newlines from LLM JSON serialization
        if '\\n' in content and '\n' not in content:
            try:
                content = content.encode('raw_unicode_escape').decode('unicode_escape')
            except Exception:
                pass

        # intercept_file_write now streams AND writes to disk directly
        intercept_file_write(filepath, content, "Global_Agent")

        _register_file_in_manifest(filepath, "unknown")
        return f"✅ Successfully wrote to sandbox/{rel}"
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"❌ Error writing to file: {str(e)}"


@tool
def read_file(filepath: str) -> str:
    """
    read_file(filepath: str) -> str
    
    Reads and returns the complete text contents of a file from the sandbox directory.
    
    IMPORTANT RULES FOR USING THIS TOOL:
    1. Use this tool to read the contents of files like JSON data, Markdown documents, or code files.
    2. The filepath must be relative to the sandbox root (e.g., 'interview/data/resume_data.json').
    3. Do NOT use this tool for binary files like PDF or DOCX (use document parser tools instead).

    Args:
        filepath (str): The relative path to the text file inside the sandbox.
        
    Returns:
        str: The raw text content of the file, or an error message if the file doesn't exist.
    """
    try:
        target_path = _get_sandboxed_path(filepath)
        with open(target_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"❌ Error reading file: {str(e)}"


# ── Manifest helper (used by write_file and namespaced factory) ───────────────

def _register_file_in_manifest(filepath: str, agent_name: str) -> None:
    """Auto-registers a written file in the shared file manifest."""
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
