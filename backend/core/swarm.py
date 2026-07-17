"""
LangNeurons — run_swarm() Protocol
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TWO MODES. ONE FUNCTION.

UNFREEZE (freeze_mode=False)  — Build the tree. Save. Exit.
    The LLM assigns system_prompt + skills to every node.
    If you already set them manually, the LLM respects that.
    No execution. No chat. Exits when tree is saved to Redis.

    # Step 1 — build (auto tree)
    await run_swarm("build a snapchat clone", freeze_mode=False, session_id="proj1")

    # Step 1 — build (your custom tree)
    root = build_my_tree()
    await run_swarm("build a snapchat clone", freeze_mode=False,
                    custom_tree=root, session_id="proj1")

FREEZE (freeze_mode=True)  — Load tree. Greet. Consent. Execute. Chat.
    Loads the tree (custom_tree arg OR from Redis). Coordinator greets the user.
    User says "yes" / "start" / anything → execution fires.
    Domain-agnostic: coding builds repo, HR does interview, research does research.
    Falls into interactive chat loop after execution.

    # Step 2 — run (from Redis)
    await run_swarm("build a snapchat clone", freeze_mode=True, session_id="proj1")

    # Step 2 — run (custom tree, skip Redis)
    root = build_hr_tree()
    await run_swarm("HR onboarding", freeze_mode=True, custom_tree=root, session_id="hr1")
"""

import asyncio
import time
import json
from collections import deque
from rich.console import Console

from core.agents.agent_node import AgentNode, redis_client
from core.agents.visualizer import Visualizer
from core.engine.orchestrator import Orchestrator
from tests.rebuild_tree import rebuild_tree_from_redis

console = Console()


def print_telemetry(msg: str) -> None:
    """Print message wrapped in telemetry tags for the frontend parser."""
    print(f"<telemetry_log>{msg}</telemetry_log>", flush=True)



# ─────────────────────────────── Tree Builders ───────────────────────────────

def build_auto_tree(total_neurons: int = 15, branching_factor: int = 2) -> AgentNode:
    """
    Builds a balanced tree with exactly `total_neurons` nodes.
    Uses breadth-first allocation with the given branching factor.
    """
    if total_neurons < 1:
        raise ValueError("Must have at least 1 neuron")

    root = AgentNode("root_neuron", "master")
    created_count = 1

    queue = deque([root])
    neuron_index = 1

    while created_count < total_neurons and queue:
        parent = queue.popleft()

        for _ in range(branching_factor):
            if created_count >= total_neurons:
                break

            child = AgentNode(f"neuron_{neuron_index}", f"slave_{neuron_index}")
            parent.add_child(child)
            queue.append(child)

            created_count += 1
            neuron_index += 1

    return root


def _count_neurons(node: AgentNode) -> int:
    """Recursively count all neurons in the tree."""
    return 1 + sum(_count_neurons(child) for child in node.children)


# ─────────────────────────────── Main Entry Point ───────────────────────────────

async def run_swarm(
    prompt: str,
    freeze_mode: bool = False,
    custom_tree: AgentNode = None,
    neuron_count: int = 15,
    branching_factor: int = 2,
    session_id: str = "default",
    clean_memory: bool = False,
    use_cache: bool = False,
    thinking_mode: bool = True,
):
    """
    LangNeurons command center — single entry point for the entire system.

    UNFREEZE mode (freeze_mode=False):
        Build the tree only. LLM generates system_prompt + skills for each node
        (or uses yours if already defined). Saves to Redis. Exits immediately.
        No execution. No chat.

    FREEZE mode (freeze_mode=True):
        Load the existing tree (custom_tree or from Redis). Coordinator greets
        the user and waits for consent. On consent, fires the tree execution.
        Domain-agnostic: coding/HR/research — whatever the tree contains.
        Falls into interactive chat loop after execution.

    Args:
        prompt:           The master task / instruction for the swarm.
        freeze_mode:      False = build tree only (unfreeze).
                          True  = execute existing tree (freeze).
        custom_tree:      Your pre-built AgentNode tree. Works in BOTH modes.
        neuron_count:     Only used in unfreeze + no custom_tree (auto tree).
        branching_factor: Only used in unfreeze + no custom_tree (auto tree).
        session_id:       Redis session key for persistence.
        clean_memory:     Clear Redis execution history before running.
        use_cache:        Skip tree rebuild if prompt is unchanged.
        thinking_mode:    If False, disables thinking/reasoning for ALL agents
                          (overrides per-agent_type defaults). Useful to cut
                          cost or latency when deep reasoning isn't needed.
    """

    # ──────────────────────────────────────────────────────────────────────────
    # UNFREEZE MODE — Build tree only. No execution. No chat.
    # ──────────────────────────────────────────────────────────────────────────
    import hashlib

    if not freeze_mode:
        # ── Cache check ───────────────────────────────────────────────────────
        prompt_hash = hashlib.sha256(prompt.strip().encode()).hexdigest()
        cache_key   = f"brief_hash:{session_id}"
        stored_hash = redis_client.get(cache_key)
        stored_hash = stored_hash.decode() if isinstance(stored_hash, bytes) else stored_hash

        if use_cache and stored_hash == prompt_hash:
            console.print(
                f"[bold yellow]⚡ Cache HIT — FORMATION_BRIEF unchanged.[/bold yellow]\n"
                f"[dim]   Skipping skill regeneration. Existing tree reused from Redis (session: {session_id}).[/dim]\n"
                f"[dim]   Run without --cache to force a full rebuild.[/dim]\n"
            )
            # Just reload and display the existing tree (import already at module top)
            cached_root = rebuild_tree_from_redis(session_id=session_id)
            if cached_root:
                Visualizer().print_tree_with_stats(cached_root)
                console.print(
                    "[bold green]✅ Tree loaded from cache.[/bold green] "
                    "[dim]Run with --freeze to execute.[/dim]\n"
                )
                return cached_root
            else:
                console.print("[yellow]⚠️  Cache miss — no tree in Redis. Rebuilding...[/yellow]")

        # ── Clear previous session state (only on a fresh build) ──────────────
        for key in redis_client.keys(f"neuron:{session_id}:*"):
            redis_client.delete(key)
        for key in redis_client.keys(f"neuron_role:{session_id}:*"):
            redis_client.delete(key)
        redis_client.delete(f"last_task:{session_id}")

        console.print(
            f"[bold yellow]🔓 Unfreeze Mode — building tree "
            f"(Cleared Session: {session_id})[/bold yellow]"
        )

        if custom_tree is not None:
            root = custom_tree
            console.print("[dim]🛠️  Using custom tree structure[/dim]")
        else:
            root = build_auto_tree(total_neurons=neuron_count, branching_factor=branching_factor)
            console.print(
                f"[dim]🛠️  Auto-generated tree: {neuron_count} neurons, "
                f"branching factor {branching_factor}[/dim]"
            )

        # Force session_id onto all nodes and initialize activation flags
        def _init_nodes(node, is_root=True):
            node.session_id = session_id
            if is_root:
                node.activate_flag = True
                if not node.dynamic_name or node.dynamic_name == "master":
                    node.dynamic_name = "task_coordinator"
            else:
                node.activate_flag = False
                node.dynamic_name = ""
                node.system_prompt = ""
            for child in node.children:
                _init_nodes(child, is_root=False)
        _init_nodes(root)

        neuron_total = _count_neurons(root)
        task_metadata = {"task": prompt, "neuron_count": neuron_total}
        redis_client.set(f"last_task:{session_id}", json.dumps(task_metadata))
        console.print(f"[dim]💾 Task metadata saved: {neuron_total} neurons[/dim]\n")

        # Save initial tree structure to Redis immediately so the frontend
        # can display and animate the tree building process in real time.
        AgentNode.save_tree_to_redis(root, session_id=session_id)
        console.print(f"[dim]💾 Initial tree saved to Redis (Session: {session_id})[/dim]\n")

        # ── Run orchestrator (LLM assigns prompts/skills to each node) ────────
        cerebrum = Orchestrator(freeze_mode=False)
        await cerebrum.start_reaction(original_task=prompt, root=root)

        # ── Persist the hash so future runs with --cache can skip rebuild ──────
        redis_client.set(cache_key, prompt_hash)
        console.print(f"[dim]🔐 FORMATION_BRIEF hash saved to cache.[/dim]")

        # Save populated tree to Redis for freeze-mode runs
        AgentNode.save_tree_to_redis(root, session_id=session_id)
        console.print(f"[dim]💾 Tree saved to Redis (Session: {session_id})[/dim]\n")

        # Print final tree state
        Visualizer().print_tree_with_stats(root)

        console.print(
            "[bold green]✅ Tree built and saved.[/bold green] "
            "[dim]Run with freeze_mode=True to execute.[/dim]\n"
        )
        return root

    # ──────────────────────────────────────────────────────────────────────────
    # FREEZE MODE — Load tree → Build state → Execute → Persist → Chat loop
    # ──────────────────────────────────────────────────────────────────────────
    from rich.panel import Panel
    from rich.prompt import Prompt as RichPrompt
    from rich.rule import Rule

    from core.engine.agent_factory import neural_agent, set_global_thinking
    from core.state.langneural_state import (
        LangneuralState, AgentNode as StateAgentNode,
        AgentExecutionRecord, AssignedTask, AgentToolReport,
    )
    from core.memory.execution_memory import persist_turn, clear_session_history

    # ── Apply global thinking mode setting BEFORE any LLM calls ────────────────
    set_global_thinking(thinking_mode)

    # ── Step 1: Load tree from Redis ──────────────────────────────────────
    print_telemetry(f"❄️  Freeze Mode — loading tree (session: {session_id})")
    root = rebuild_tree_from_redis(session_id=session_id)
    if root is None:
        print_telemetry(
            "❌ No tree found in Redis. "
            "Run with freeze_mode=False first to build one."
        )
        return None

    # ── Step 2: Initialize agents (loads tools onto each node) ───────────
    print_telemetry("Initialising agents...")
    def _restore(node):
        node.session_id = session_id
        try:
            node.initialize_agent()
        except Exception as e:
            print_telemetry(f"⚠️  Failed to init {node.common_name}: {e}")
        for child in node.children:
            _restore(child)
    _restore(root)

    # ── Step 3: Build agent_tools and agent_hierarchy from tree ──────────
    def _extract_tools(node) -> dict:
        tools_map = {}
        tool_names = [t.name for t in node.tools] if hasattr(node, "tools") and node.tools else []
        tools_map[node.common_name] = tool_names
        for child in node.children:
            tools_map.update(_extract_tools(child))
        return tools_map

    def _extract_hierarchy(node) -> dict:
        hierarchy_map = {}
        hierarchy_map[node.common_name] = StateAgentNode(
            supervisor=node.parent.common_name if node.parent else "human",
            subordinates=[child.common_name for child in node.children],
        )
        for child in node.children:
            hierarchy_map.update(_extract_hierarchy(child))
        return hierarchy_map

    agent_tools_map = _extract_tools(root)
    agent_hierarchy_map = _extract_hierarchy(root)

    # ── Step 4: Greeting ──────────────────────────────────────────────────
    if clean_memory:
        clear_session_history(session_id)
        print_telemetry("🧹 Execution history cleared for a fresh start.")

    coordinator_role = root.dynamic_name or root.common_name
    greeting_text = (
        f"👋 I'm {coordinator_role}\n\n"
        f"Ready to execute. Type your task — or 'exit' to quit.\n"
        f"Commands: 'history' to view agent memory | 'clear' to reset"
    )
    print(f"<agent_response agent='{coordinator_role}'>\n{greeting_text}\n</agent_response>", flush=True)

    print_telemetry("💬 Chat — type 'exit' to quit")

    # ── Step 5: Chat loop ─────────────────────────────────────────────────
    from core.memory.execution_memory import load_tool_report
    global_team_tool_report = load_tool_report(session_id) or {}

    while True:
        try:
            user_input = input("\n\033[1;36mYou:\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print_telemetry("👋 Session ended.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "bye"):
            print_telemetry("👋 Goodbye!")
            break

        if user_input.lower() == "history":
            from core.memory.execution_memory import load_agent_history
            history = load_agent_history(session_id, root.common_name)
            print_telemetry(f"📜 {root.common_name} History:\n{history or '(No history yet)'}")
            continue

        if user_input.lower() == "clear":
            clear_session_history(session_id)
            global_team_tool_report = {}
            print_telemetry("✅ Execution history cleared.")
            continue

        # ── Fire the new state-driven execution engine ────────────────────
        try:
            # Build fresh LangneuralState for this turn, but preserve tool ledger
            state = LangneuralState(
                human_prompt=user_input,
                agent_tools=agent_tools_map,
                agent_hierarchy=agent_hierarchy_map,
                team_tool_report=global_team_tool_report,
            )

            # Fill root agent's inbox
            state.team_execution_report[root.common_name] = AgentExecutionRecord(
                task_received=AssignedTask(
                    supervisor="human",
                    task_instructions=user_input,
                    response_provided="pending",
                )
            )

            # Execute — state flows down the tree and back up
            print_telemetry("⚙️  Executing...")
            state = await neural_agent(
                agent_name=root.common_name,
                state=state,
                session_id=session_id,
                root_node=root,
            )

            # Extract final response
            root_record = state.team_execution_report.get(root.common_name)
            final_response = (
                root_record.task_received.response_provided
                if root_record and root_record.task_received
                else "(No response generated)"
            )

            # Store memory for next turn
            from core.memory.execution_memory import persist_turn, persist_tool_report, load_tool_report
            persist_turn(session_id, state.team_execution_report)

            # Persist tool report to the global loop variable AND Redis
            global_team_tool_report = state.team_tool_report
            persist_tool_report(session_id, global_team_tool_report)

            # Flush team_execution_report only — team_tool_report persists
            state.team_execution_report = {}

            # Display response
            print(f"<agent_response agent='{coordinator_role}'>\n{final_response}\n</agent_response>", flush=True)

        except Exception as e:
            import traceback
            print_telemetry(f"❌ Error: {e}")
            print_telemetry(f"{traceback.format_exc()}")

    return root




# ─────────────────────────────── CLI ───────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Synaptron Swarm — Command Center")
    parser.add_argument("prompt", help="The task / instruction for the swarm")
    parser.add_argument("--freeze", action="store_true", default=False,
                        help="Freeze mode: reuse existing tree (default: unfreeze)")
    parser.add_argument("--neurons", type=int, default=15,
                        help="Number of neurons for auto tree (default: 15)")
    parser.add_argument("--branching", type=int, default=2,
                        help="Branching factor for auto tree (default: 2)")
    parser.add_argument("--no-thinking", action="store_true", default=False,
                        help="Disable thinking/reasoning mode for all agents")

    args = parser.parse_args()

    asyncio.run(run_swarm(
        prompt=args.prompt,
        freeze_mode=args.freeze,
        neuron_count=args.neurons,
        branching_factor=args.branching,
        thinking_mode=not args.no_thinking,
    ))
