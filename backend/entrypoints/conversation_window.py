"""
conversation_window.py
━━━━━━━━━━━━━━━━━━━━━━
Real-time Agent Conversation Tracer.

Run this in a SEPARATE terminal alongside run_conversation.py to watch
the internal agent-to-agent communication as it happens in real time.

It tails the SharedMemory log from Redis and prints each new message
with color-coded agent names so you can trace the exact flow:

    🔵 [user]                    → hii
    🟡 [Interview_Router]        → delegating to Intro_Agent: Greet the candidate warmly...
    🟢 [Intro_Agent]             → Hello! Welcome to the interview. What is your name?
    🔵 [user]                    → I'm Priya
    🟢 [Intro_Agent]             → Nice to meet you Priya! Let me hand you over to our HR team.
    ⚪ [system]                  → Intro_Agent completed: Introduction done. Candidate: Priya

Usage:
    python conversation_window.py                    # default session
    python conversation_window.py --session hr_session
    python conversation_window.py --clear            # clear history and start fresh
"""

import time
import sys
import json
import argparse
from datetime import datetime

from rich.console import Console
from rich.text import Text
from rich.rule import Rule
from core.engine.memory import RedisClient

console = Console()

# ── Colour palette per role type ──────────────────────────────────────────────
# Role → (icon, rich_color)
_DEFAULT_COLOR = ("🤖", "white")

_ROLE_STYLES: dict[str, tuple[str, str]] = {
    "user":       ("👤", "bold cyan"),
    "system":     ("⚙️ ", "dim white"),
    # HR tree — custom role names map directly
    "Interview_Router":    ("🔀", "bold yellow"),
    "Intro_Agent":         ("😊", "bold green"),
    "Mid_Flow_Agent":      ("🌊", "bold blue"),
    "Post_Eval_Agent":     ("🏁", "bold magenta"),
    "HR_Manager":          ("👔", "bold red"),
    "Resume_Parser":       ("📄", "bold cyan"),
    "Technical_Interviewer": ("💻", "bold bright_blue"),
    "Interview_Evaluator": ("🎯", "bold bright_red"),
    # Fallback for auto-generated trees (any agent name)
    "task_coordinator":    ("🧠", "bold yellow"),
}

def _style_for(role: str) -> tuple[str, str]:
    """Return (icon, color) for a given role name."""
    # Exact match
    if role in _ROLE_STYLES:
        return _ROLE_STYLES[role]
    # Check fragments (e.g. "RouterAgent" contains "Router")
    for key, style in _ROLE_STYLES.items():
        if key.lower() in role.lower() or role.lower() in key.lower():
            return style
    return _DEFAULT_COLOR


def _format_message(role: str, content: str) -> Text:
    icon, color = _style_for(role)
    text = Text()
    timestamp = datetime.now().strftime("%H:%M:%S")
    text.append(f"  {timestamp}  ", style="dim")
    text.append(f"{icon} [{role}]", style=color)
    text.append("  →  ", style="dim")

    # Truncate very long system messages
    display_content = content
    if role == "system" and len(content) > 200:
        display_content = content[:200] + "…"

    if role == "user":
        text.append(display_content, style="bold cyan")
    elif role == "system":
        text.append(display_content, style="dim italic")
    else:
        text.append(display_content, style="white")

    return text


def watch(session_id: str, poll_interval: float = 0.5) -> None:
    """Tail the SharedMemory Redis log and print new messages as they arrive."""
    redis = RedisClient().get_client()
    mem_key = f"memory:{session_id}:history"

    console.print(Rule(f"[bold]🔍 Synaptron Conversation Tracer — session: {session_id}[/bold]"))
    console.print("[dim]Watching for agent activity... (Ctrl+C to stop)[/dim]\n")

    seen_count = 0

    try:
        while True:
            raw_entries = redis.lrange(mem_key, 0, -1)
            current_count = len(raw_entries)

            if current_count > seen_count:
                # Print newly added entries
                new_entries = raw_entries[seen_count:]
                for raw in new_entries:
                    try:
                        entry = json.loads(raw.decode())
                        role = entry.get("role", "unknown")
                        content = entry.get("content", "")
                        console.print(_format_message(role, content))
                    except Exception:
                        pass
                seen_count = current_count

            time.sleep(poll_interval)

    except KeyboardInterrupt:
        console.print("\n[dim]Tracer stopped.[/dim]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synaptron Conversation Tracer — watch agent communication in real time"
    )
    parser.add_argument(
        "--session", "-s",
        default="hr_session",
        help="Session ID (default: hr_session)"
    )
    parser.add_argument(
        "--clear", "-c",
        action="store_true",
        help="Clear the conversation history for this session and exit"
    )
    parser.add_argument(
        "--poll", "-p",
        type=float,
        default=0.5,
        help="Poll interval in seconds (default: 0.5)"
    )
    args = parser.parse_args()

    if args.clear:
        redis = RedisClient().get_client()
        redis.delete(f"memory:{args.session}:history")
        console.print(f"[green]✅ Cleared conversation history for session: {args.session}[/green]")
        sys.exit(0)

    # ── Always clear previous conversation on startup ──
    redis = RedisClient().get_client()

    # Clear conversation history
    redis.delete(f"memory:{args.session}:history")

    # Clear agent metadata keys for this session
    meta_keys = redis.keys(f"agent_meta:{args.session}:*")
    for k in meta_keys:
        redis.delete(k)

    console.print(f"[green]🧹 Cleared previous conversation & metadata for session: {args.session}[/green]")

    watch(session_id=args.session, poll_interval=args.poll)


if __name__ == "__main__":
    main()
