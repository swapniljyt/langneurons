"""
core/tools/execution/runner.py
───────────────────────────────
Shell execution tool (execute_command) and session-scoped
suggest_fix tool factory for Runner agents.
"""

import subprocess
from langchain_core.tools import tool


# Commands known to be long-running servers — always launched in background
_BACKGROUND_COMMANDS = (
    "npm start", "npm run dev", "npm run start", "next dev", "next start",
    "python -m uvicorn", "uvicorn", "flask run", "gunicorn",
    "python manage.py runserver", "python -m http.server", "python3 -m http.server"
)


@tool
def execute_command(command: str) -> str:
    """
    Executes a shell command securely inside the 'sandbox' directory.
    Use this to run tests, compile files, install packages, or verify generated code.

    Long-running server commands (npm start, npm run dev, uvicorn, etc.) are
    automatically launched in the background and the tool immediately returns
    the expected local URL without blocking.

    Args:
        command: The shell command to execute (e.g. 'npm run build', 'npm start').
    """
    import os
    import re
    from ..filesystem.read_write import SANDBOX_DIR

    try:
        from rich.console import Console
        console = Console()
        console.print(f"\n[bold yellow]💻 SYSTEM EXECUTION:[/bold yellow] [cyan]{command}[/cyan]")
    except ImportError:
        print(f"\n💻 SYSTEM EXECUTION: {command}")
        console = None

    # ── SANDBOX SECURITY ENFORCEMENT & HARDENING ──
    # 1. Path traversal protection: Block going above the sandbox
    if ".." in command:
        err_msg = "❌ Security Violation: Path traversal ('..') is strictly blocked."
        if console:
            console.print(f"[bold red]{err_msg}[/bold red]\n")
        return err_msg

    # 2. Block dangerous destructive commands
    banned_patterns = [
        r"\brm\b",          # Block remove
        r"\bmv\b",          # Block move
        r"\bshred\b",       # Block secure deletion
        r"\bdd\b",          # Block raw disk write
        r"\bmkfs\b",        # Block filesystem creation
        r"\bsudo\b",        # Block root escalation
        r"\bchown\b",       # Block ownership change
        r"\bkill\b",        # Block process termination
        r"\bpkill\b",       # Block process termination
        r"\bshutdown\b",    # Block shutdown
        r"\breboot\b",      # Block reboot
    ]
    for pattern in banned_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            err_msg = f"❌ Security Violation: Command matches blocked security pattern '{pattern}'."
            if console:
                console.print(f"[bold red]{err_msg}[/bold red]\n")
            return err_msg

    # 3. Docker security validation (Only read-only Docker commands allowed)
    if "docker" in command.lower():
        blocked_docker_patterns = [
            r"\bdocker\s+(kill|stop|rm|rmi|system|volume|network|exec|run|prune)\b",
            r"\bdocker-compose\s+(kill|stop|down|rm)\b"
        ]
        for pattern in blocked_docker_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                err_msg = "❌ Security Violation: Destructive Docker commands (stop, rm, kill, down, prune) are blocked."
                if console:
                    console.print(f"[bold red]{err_msg}[/bold red]\n")
                return err_msg

    # 4. Absolute path validation: Block absolute paths that do not target the sandbox or standard binary/libs
    words = command.split()
    for word in words:
        if word.startswith("/") and not word.startswith(SANDBOX_DIR):
            # Check if it's pointing to standard safe command directories or standard interpreters
            safe_prefixes = ["/bin", "/usr/bin", "/usr/sbin", "/usr/lib", "/lib", "/usr/local/bin"]
            if not any(word.startswith(prefix) for prefix in safe_prefixes):
                err_msg = f"❌ Security Violation: Accessing absolute path '{word}' outside the sandbox is blocked."
                if console:
                    console.print(f"[bold red]{err_msg}[/bold red]\n")
                return err_msg

    cmd_lower = command.strip().lower()
    is_server = any(cmd_lower.startswith(bg) or bg in cmd_lower for bg in _BACKGROUND_COMMANDS)

    if is_server:
        try:
            import time
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=SANDBOX_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            time.sleep(2)
            msg = f"🚀 Server started in background (PID {proc.pid})"
            if console:
                console.print(f"[bold green]{msg}[/bold green]")
                console.print(f"[bold green]   → Local:   http://localhost:3000[/bold green]\n")
            else:
                print(msg)
            return (
                f"✅ Server started in background (PID {proc.pid}).\n"
                f"Local URL: http://localhost:3000\n"
                f"Note: This is a long-running process. Do NOT call npm start again."
            )
        except Exception as e:
            return f"❌ Failed to start server: {e}"

    # Normal finite commands
    try:
        from ..filesystem.read_write import SANDBOX_DIR
        result = subprocess.run(
            command, shell=True, cwd=SANDBOX_DIR,
            capture_output=True, text=True, timeout=120,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[STDERR]:\n{result.stderr}"

        if output.strip():
            if console:
                console.print(f"[dim]{output.strip()}[/dim]\n")
            else:
                print(output.strip())
        else:
            msg = "(Command completed with no output)"
            if console:
                console.print(f"[dim]{msg}[/dim]\n")
            else:
                print(msg)

        return output if output.strip() else "Command executed successfully in sandbox/ with no output."
    except subprocess.TimeoutExpired:
        return "❌ Command timed out after 120 seconds."
    except Exception as e:
        return f"❌ Error executing command: {str(e)}"


def create_runner_tools(session_id: str) -> list:
    """
    Factory: returns session-scoped runner tools.
    Currently produces: [suggest_fix]

    Args:
        session_id: The active swarm session ID, used to query incident memory.
    """

    @tool
    def suggest_fix(error_snippet: str) -> str:
        """
        Queries the organizational Incident Memory for past solutions to similar errors.
        Use this when a build command or test fails and you don't know how to fix it.

        Args:
            error_snippet: The relevant portion of the error message or stack trace.
                           Keep it under 50 words for best matching.
        """
        try:
            from ...memory.incident_log import IncidentLogStore
            store   = IncidentLogStore(session_id=session_id)
            incidents = store.get_recent_incidents(limit=20)
            search_terms = error_snippet.lower().split()
            matches = []
            for inc in incidents:
                inc_text = f"{inc['escalation_reason']} {inc['error_snippet']}".lower()
                score = sum(1 for term in search_terms if len(term) > 3 and term in inc_text)
                if score > 0:
                    matches.append((score, inc))
            if not matches:
                return "❌ No past incidents found matching this error. Escalate to the human user."
            matches.sort(key=lambda x: x[0], reverse=True)
            response = "✅ Found past resolutions for similar errors:\n\n"
            for _, inc in matches[:3]:
                response += (
                    f"- Past Error: {inc['escalation_reason']}\n"
                    f"  Resolution: {inc['resolution']}\n"
                    f"  Root Cause: {inc['root_cause']}\n\n"
                )
            return response
        except Exception as e:
            return f"❌ Error querying incident memory: {str(e)}"

    return [suggest_fix]
