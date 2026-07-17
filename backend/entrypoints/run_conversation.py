import sys, os as _os
# Ensure the project root (langneurons/) is always in sys.path,
# regardless of which directory the script is run from.
_PROJECT_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

"""
run_conversation.py
━━━━━━━━━━━━━━━━━━━
User-Facing Chat Window for Synaptron Agent Trees.

Loads the agent tree from Redis (built by hr_main.py or main.py),
then opens an interactive chat loop where the user talks with the tree.

The execution is deterministic — every routing decision is made by the
agent's structured output, not by an autonomous planner.

Usage:
    Step 1 (build tree):        python hr_main.py
    Step 2 (chat):              python run_conversation.py
    Step 3 (trace internals):   python conversation_window.py   [separate terminal]

Options:
    --session     Session ID to load tree from (default: hr_session)
    --clear-mem   Clear conversation history before starting
"""

import asyncio
import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.prompt import Prompt

from tests.rebuild_tree import rebuild_tree_from_redis
from core.agents.agent_node import AgentNode, redis_client
# ExecutionEngine and SharedMemory removed — use swarm.py freeze mode instead
# from core.runtime.execution_engine import ExecutionEngine  ← DELETED
# from core.runtime.shared_memory import SharedMemory         ← DELETED

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# Tree Loader
# ─────────────────────────────────────────────────────────────────────────────

def _load_tree(session_id: str) -> AgentNode | None:
    """Rebuild the agent tree from Redis and initialise all agents."""
    console.print(f"\n[dim]🏗️  Loading agent tree from Redis (session: {session_id})...[/dim]")

    root = rebuild_tree_from_redis(session_id=session_id)
    if root is None:
        console.print(
            Panel(
                f"[red]❌ No agent tree found in Redis for session '{session_id}'.\n\n"
                f"Run [bold]python hr_main.py[/bold] first to build and save the tree.[/red]",
                title="Tree Not Found",
                border_style="red",
            )
        )
        return None

    # Restore roles and initialise LangGraph agents
    def _restore(node: AgentNode) -> None:
        node.load_role_from_redis()
        try:
            node.initialize_agent()
        except Exception as e:
            console.print(f"[red]⚠️  Failed to init agent for {node.common_name}: {e}[/red]")
        for child in node.children:
            _restore(child)

    _restore(root)

    # Count neurons
    def _count(n: AgentNode) -> int:
        return 1 + sum(_count(c) for c in n.children)

    total = _count(root)
    console.print(f"[green]✅ Tree loaded: {total} agents ready[/green]")
    return root


# ─────────────────────────────────────────────────────────────────────────────
# Chat Loop
# ─────────────────────────────────────────────────────────────────────────────

async def chat_loop(engine: ExecutionEngine, session_id: str) -> None:
    """Interactive chat loop — user types, agent tree responds."""

    console.print(Rule("[bold green]💬 LangNeurons Chat — Type 'exit' to quit[/bold green]"))
    console.print(
        "[dim]Commands: memory | meta | timeline | responsibilities | clear | exit[/dim]\n"
    )

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Session ended.[/dim]")
            break

        user_input = user_input.strip()

        if not user_input:
            continue

        # ── Special commands ───────────────────────────────────────────────────
        if user_input.lower() in ("exit", "quit", "bye"):
            console.print("[dim]👋 Goodbye![/dim]")
            break

        if user_input.lower() == "memory":
            history = engine.memory.get_history()
            if not history:
                console.print("[dim](No conversation history yet)[/dim]")
            else:
                console.print(Panel(
                    engine.memory.format_for_prompt(),
                    title="📜 Shared Conversation Memory",
                    border_style="dim"
                ))
            continue

        if user_input.lower() == "meta":
            all_meta = engine.meta_store.get_all()
            import json
            console.print(Panel(
                json.dumps(all_meta, indent=2),
                title="🧠 Agent Metadata States",
                border_style="dim"
            ))
            continue

        if user_input.lower() == "timeline":
            shared_ctx = engine.bridge.get_shared_context(last_n=50)
            console.print(Panel(
                shared_ctx["timeline"],
                title="📜 Organizational Timeline",
                border_style="bright_cyan"
            ))
            continue

        if user_input.lower() == "responsibilities":
            shared_ctx = engine.bridge.get_shared_context()
            output = (
                f"ACTIVE RESPONSIBILITIES:\n{shared_ctx['responsibilities']}\n\n"
                f"TEAM KNOWLEDGE:\n{shared_ctx['metadata_registry']}"
            )
            console.print(Panel(
                output,
                title="📋 Responsibility Board",
                border_style="bright_yellow"
            ))
            continue

        if user_input.lower() == "context":
            # ContextPacketBuilder removed — use execution_memory.load_agent_history() instead
            console.print("[yellow]context_packet has been removed. Use 'history' command in swarm.py.[/yellow]")

            builder = ContextPacketBuilder(session_id=session_id)
            packet = builder.build(
                agent_name=engine.root.common_name,
                agent_role=engine.root.dynamic_name or "Router",
            )
            console.print(Panel(
                packet if packet.strip() else "(Context packet is empty — no prior activity)",
                title="📦 Context Packet (Root Agent View)",
                border_style="dim"
            ))
            continue

        if user_input.lower() == "clear":
            engine.memory.clear()
            engine.meta_store.reset_all()
            engine.bridge.clear()
            console.print("[green]✅ Memory, metadata, and organizational state cleared.[/green]")
            continue

        # ── Normal chat turn ───────────────────────────────────────────────────
        try:
            response = await engine.chat(user_input)
            # Response was already printed by engine — nothing more needed here
        except Exception as e:
            console.print(f"[red]❌ Error during agent execution: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")


# ─────────────────────────────────────────────────────────────────────────────
# Auto-Execution Phase
# ─────────────────────────────────────────────────────────────────────────────

async def auto_execute(engine: ExecutionEngine, root: AgentNode) -> None:
    """
    Auto-execute the tree on startup.

    Reads the root's subtask (the full project specification assigned during
    main.py) and triggers the entire execution pipeline. All agents execute
    their pre-assigned subtasks through the hierarchy.

    For build trees: agents write files, build the app, and report completion.
    For conversational trees: agents adopt their personas and greet the user.
    """
    # Get the initial task from the root node
    initial_task = root.subtask_provided or root.main_task or None

    if not initial_task:
        console.print("[dim]ℹ️  No subtask found on root — skipping auto-execution.[/dim]")
        return

    console.print(Panel(
        f"[bold white]🚀 Auto-Executing: All agents activating their subtasks...[/bold white]\n\n"
        f"[dim]{initial_task[:200]}{'...' if len(initial_task) > 200 else ''}[/dim]",
        border_style="bright_magenta",
        title="⚡ Swarm Auto-Start",
    ))

    try:
        response = await engine.auto_build(initial_task)
    except Exception as e:
        console.print(f"[red]❌ Auto-execution failed: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

    console.print(Rule("[bold green]✅ Auto-execution complete — entering interactive mode[/bold green]"))


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synaptron Chat — talk with your agent tree"
    )
    parser.add_argument(
        "--session", "-s",
        default="hr_session",
        help="Session ID to load from Redis (default: hr_session)"
    )
    parser.add_argument(
        "--clear-mem", "-c",
        action="store_true",
        help="Clear conversation history and agent metadata before starting"
    )
    parser.add_argument(
        "--no-auto", "-n",
        action="store_true",
        help="Skip auto-execution and go straight to interactive chat"
    )
    args = parser.parse_args()

    # ── Banner ─────────────────────────────────────────────────────────────────
    console.print(Panel(
        "[bold white]Synaptron Agent Runtime[/bold white]\n"
        "[dim]Deterministic · Conversational · Production-grade[/dim]",
        border_style="bright_blue",
        padding=(1, 4),
    ))

    # ── Load tree ──────────────────────────────────────────────────────────────
    root = _load_tree(args.session)
    if root is None:
        sys.exit(1)

    # ── Engine setup ────────────────────────────────────────────────────────────
    # ExecutionEngine removed — run_conversation.py is deprecated.
    # Use: from core.swarm import run_swarm; await run_swarm(prompt=..., freeze_mode=True)
    console.print(Panel(
        "[yellow]⚠️  run_conversation.py is deprecated.[/yellow]\n\n"
        "The ExecutionEngine has been replaced by the new neural_agent architecture.\n"
        "Use [bold]swarm.py with freeze_mode=True[/bold] to run the agent tree.",
        title="Deprecated Entrypoint",
        border_style="yellow",
    ))
    sys.exit(0)

    if args.clear_mem:
        engine.memory.clear()
        engine.meta_store.reset_all()
        engine.bridge.clear()
        console.print("[green]✅ Cleared memory, metadata, and organizational state.[/green]")

    # ── Auto-execute: run all agents on their subtasks ──────────────────────────
    if not args.no_auto:
        await auto_execute(engine, root)

    # ── Interactive chat for follow-ups ─────────────────────────────────────────
    await chat_loop(engine, session_id=args.session)


if __name__ == "__main__":
    asyncio.run(main())

