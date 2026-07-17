"""
core/inspect_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive CLI tool to inspect LangNeurons agents' state, execution history,
and 3-tier memory (Long-Term, Medium-Term, Short-Term) in real-time.
"""

import sys
import os
import json

# Ensure project root is in sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from core.engine.memory import RedisClient
from core.agents.agent_node import AgentNode
from tests.rebuild_tree import rebuild_tree_from_redis

console = Console()
redis = RedisClient().get_client()

def extract_tools(node) -> dict:
    tools_map = {}
    tool_names = [t.name for t in node.tools] if hasattr(node, "tools") and node.tools else []
    tools_map[node.common_name] = tool_names
    for child in node.children:
        tools_map.update(extract_tools(child))
    return tools_map

def extract_hierarchy(node) -> dict:
    hierarchy_map = {}
    hierarchy_map[node.common_name] = {
        "supervisor": node.parent.common_name if node.parent else "human",
        "subordinates": [child.common_name for child in node.children]
    }
    for child in node.children:
        hierarchy_map.update(extract_hierarchy(child))
    return hierarchy_map

def view_state(session_id: str):
    console.print(f"\n[bold cyan]🔍 Fetching Global State for Session: {session_id}[/bold cyan]")

    root = rebuild_tree_from_redis(session_id=session_id)
    if not root:
        console.print(f"[bold red]❌ No tree found in Redis for '{session_id}'.[/bold red]")
        return
        
    # Initialize the agents to attach their tools properly
    def _init(node):
        try:
            node.session_id = session_id
            node.initialize_agent()
        except:
            pass
        for child in node.children:
            _init(child)
    _init(root)

    agent_tools = extract_tools(root)
    agent_hierarchy = extract_hierarchy(root)
    
    # Reconstruct execution report from Redis history
    team_execution_report = {}
    team_tool_report = {}
    human_prompt = ""
    
    for agent in agent_tools.keys():
        key = f"execution_history:{session_id}:{agent}"
        raw = redis.get(key)
        if raw:
            try:
                history = json.loads(raw.decode("utf-8"))
                if history:
                    # Get the most recent turn
                    latest_turn = history[-1]
                    
                    task_rec = latest_turn.get("task_received")
                    if task_rec:
                        task_rec.pop("timestamp", None)
                        if task_rec.get("supervisor") == "human" and agent == root.common_name:
                            human_prompt = task_rec.get("task_instructions", "")
                    
                    tasks_del = latest_turn.get("tasks_delegated", [])
                    for d in tasks_del:
                        d.pop("timestamp", None)
                        
                    team_execution_report[agent] = {
                        "task_received": task_rec,
                        "tasks_delegated": tasks_del
                    }
            except Exception as e:
                team_execution_report[agent] = {"error": str(e)}
                
    # Reconstruct tool report
    raw_tool_report = redis.get(f"tool_report:{session_id}")
    if raw_tool_report:
        try:
            team_tool_report = json.loads(raw_tool_report.decode("utf-8"))
        except:
            pass
            
    # Ensure all agents have at least an empty stub if not present in tool_report
    for agent in agent_tools.keys():
        if agent not in team_tool_report:
            team_tool_report[agent] = {
                "read": [],
                "write": [],
                "edited": [],
                "error": []
            }

    # Build the massive state JSON
    global_state = {
        "human_prompt": human_prompt or "(No human prompt yet)",
        "agent_tools": agent_tools,
        "agent_hierarchy": agent_hierarchy,
        "team_execution_report": team_execution_report,
        "team_tool_report": team_tool_report
    }

    # Print the exact requested format
    console.print("\n[bold yellow]==========================================[/bold yellow]")
    console.print("[bold yellow] GLOBAL STATE OBJECT (LangneuralState)[/bold yellow]")
    console.print("[bold yellow]==========================================[/bold yellow]\n")
    
    console.print_json(data=global_state)

def view_history(session_id: str):
    console.print(f"\n[bold cyan]📜 Fetching Chronological Execution History for Session: {session_id}[/bold cyan]")
    
    pattern = f"execution_history:{session_id}:*"
    keys = redis.keys(pattern)
    
    if not keys:
        console.print(f"[bold red]❌ No history found in Redis for '{session_id}'.[/bold red]")
        return
        
    for key in keys:
        agent_name = key.decode("utf-8").split(":")[-1]
        raw = redis.get(key)
        if raw:
            try:
                history = json.loads(raw.decode("utf-8"))
                console.print(f"\n[bold magenta]🤖 Agent: {agent_name}[/bold magenta] ({len(history)} turns recorded)")
                for i, turn in enumerate(history, start=1):
                    received = turn.get("task_received")
                    delegated = turn.get("tasks_delegated", [])
                    
                    ts = received.get("timestamp", "?") if received else "?"
                    console.print(f"  [dim]TURN {i} ({ts})[/dim]")
                    
                    if received:
                        console.print(f"    [bold green]Received from {received.get('supervisor')}:[/bold green] {received.get('task_instructions')}")
                        console.print(f"    [bold yellow]Responded:[/bold yellow] {received.get('response_provided')}")
                    
                    for d in delegated:
                        console.print(f"    [bold cyan]Delegated to {d.get('subordinate_agent')}:[/bold cyan] {d.get('task_delivered')}")
                        console.print(f"      ↳ [dim]Response:[/dim] {d.get('task_response')}")
                        
                console.print("[dim]" + "─"*50 + "[/dim]")
            except Exception as e:
                console.print(f"[red]Error parsing history for {agent_name}: {e}[/red]")


def view_tiered_memory(session_id: str):
    """
    Displays the 3-Tier Decaying Memory architecture (Long-Term, Medium-Term, Short-Term)
    for a selected agent, or for all agents in the session.
    """
    console.print(f"\n[bold cyan]🧠 Fetching 3-Tier Memory (Long/Medium/Short Term) for Session: {session_id}[/bold cyan]")
    
    pattern = f"execution_history:{session_id}:*"
    keys = redis.keys(pattern)
    
    if not keys:
        console.print(f"[bold red]❌ No history found in Redis for '{session_id}'.[/bold red]")
        return
        
    agents = sorted([key.decode("utf-8").split(":")[-1] for key in keys])
    
    console.print("\n[bold white]Select which agent's conversation history you want to see:[/bold white]")
    console.print("  [0] [bold green]View ALL Agents[/bold green]")
    for idx, agent in enumerate(agents, start=1):
        console.print(f"  [{idx}] {agent}")
        
    choice_str = Prompt.ask("\nChoose", choices=["0"] + [str(i) for i in range(1, len(agents) + 1)], default="0", show_choices=False)
    choice = int(choice_str)
    
    selected_agents = []
    if choice == 0:
        selected_agents = agents
    else:
        selected_agents = [agents[choice - 1]]
        
    for agent_name in selected_agents:
        key = f"execution_history:{session_id}:{agent_name}"
        raw = redis.get(key)
        if raw:
            try:
                history = json.loads(raw.decode("utf-8"))
                
                long_term_block = None
                medium_term_block = None
                short_term_turns = []
                
                for turn in history:
                    tier = turn.get("memory_tier")
                    if tier == "long_term":
                        long_term_block = turn
                    elif tier == "medium_term":
                        medium_term_block = turn
                    elif "compressed_summary" in turn: # Legacy support
                        medium_term_block = {
                            "summary": turn["compressed_summary"],
                            "turns_covered": turn.get("turns_covered", 10)
                        }
                    else:
                        short_term_turns.append(turn)
                
                console.print(f"\n[bold magenta]🤖 AGENT: {agent_name}[/bold magenta]")
                console.print("[dim]" + "═"*60 + "[/dim]")
                
                # 🏛️ 1. Long Term (10% compression tier)
                if long_term_block:
                    console.print(Panel(
                        f"[yellow]{long_term_block['summary']}[/yellow]",
                        title=f"🏛️  [bold yellow]LONG-TERM DECAYED MEMORY[/bold yellow] (Covers {long_term_block['turns_covered']} oldest turns)",
                        border_style="yellow",
                        padding=(1, 2)
                    ))
                else:
                    console.print("[dim]🏛️  Long-Term Memory: None (swapped out/not accumulated yet)[/dim]")
                
                # 📚 2. Medium Term (50% compression tier)
                if medium_term_block:
                    console.print(Panel(
                        f"[cyan]{medium_term_block['summary']}[/cyan]",
                        title=f"📚  [bold cyan]MEDIUM-TERM DECAYED MEMORY[/bold cyan] (Covers {medium_term_block['turns_covered']} older turns)",
                        border_style="cyan",
                        padding=(1, 2)
                    ))
                else:
                    console.print("[dim]📚  Medium-Term Memory: None (swapped out/not accumulated yet)[/dim]")
                
                # ⚡ 3. Short Term (Raw uncompressed turns tier)
                if short_term_turns:
                    console.print(f"\n⚡  [bold green]SHORT-TERM MEMORY (Raw Active Turns)[/bold green] — {len(short_term_turns)} turns:")
                    for i, turn in enumerate(short_term_turns, start=1):
                        received = turn.get("task_received")
                        delegated = turn.get("tasks_delegated", [])
                        ts = received.get("timestamp", "?") if received else "?"
                        
                        console.print(f"  [bold green]• Turn {i} ({ts})[/bold green]")
                        if received:
                            console.print(f"      [dim]Received from {received.get('supervisor')}:[/dim] [white]{received.get('task_instructions')}[/white]")
                            console.print(f"      [bold yellow]↳ Responded:[/bold yellow] [dim]{received.get('response_provided')}[/dim]")
                        
                        for d in delegated:
                            console.print(f"      [bold cyan]↳ Delegated to {d.get('subordinate_agent')}:[/bold cyan] {d.get('task_delivered')}")
                            console.print(f"        [dim]└─ Subordinate Response:[/dim] {d.get('task_response')}")
                else:
                    console.print("[dim]⚡  Short-Term Memory: None[/dim]")
                    
                console.print("[dim]" + "─"*60 + "[/dim]\n")
                
            except Exception as e:
                console.print(f"[red]Error parsing tiered memory for {agent_name}: {e}[/red]")


def view_llm_context(session_id: str):
    """
    Show the FULL unified 9-section system prompt for any agent.
    """
    agent_name = Prompt.ask("Enter the Agent Name (e.g., RouterAgent or CasualIntroductionAgent)")
    console.print(f"\n[bold cyan]🧠 Building Full 9-Section Prompt for: [white]{agent_name}[/white] | Session: {session_id}[/bold cyan]")

    # Rebuild tree from Redis
    root = rebuild_tree_from_redis(session_id=session_id)
    if not root:
        console.print(f"[bold red]❌ No tree found in Redis for '{session_id}'. Run the session first.[/bold red]")
        return

    # Initialize agents so tools are attached
    def _init(node):
        try:
            node.session_id = session_id
            node.initialize_agent()
        except Exception:
            pass
        for child in node.children:
            _init(child)
    _init(root)

    # Find the target node
    target_node = root.find_neuron_by_name(agent_name)
    if not target_node:
        console.print(f"[bold red]❌ Agent '{agent_name}' not found in the tree.[/bold red]")
        console.print("[dim]Available agents:[/dim]")
        def _print_tree(node, indent=0):
            console.print(f"{'  ' * indent}• {node.common_name}  ({node.dynamic_name})")
            for child in node.children:
                _print_tree(child, indent + 1)
        _print_tree(root)
        return

    # Load live Redis state
    from core.memory.execution_memory import load_agent_history
    from core.engine.prompt_builder import build_agent_prompt

    my_history = load_agent_history(session_id, agent_name)

    raw_tool_report = redis.get(f"tool_report:{session_id}")
    team_tool_report_raw: dict = {}
    if raw_tool_report:
        try:
            team_tool_report_raw = json.loads(raw_tool_report.decode("utf-8"))
        except Exception:
            pass

    tool_names = [t.name for t in target_node.tools] if hasattr(target_node, "tools") and target_node.tools else []

    # Determine supervisor name from node tree
    supervisor_name = target_node.parent.common_name if target_node.parent else "human"

    # Build the full 9-section prompt
    try:
        full_prompt = build_agent_prompt(
            agent_node=target_node,
            session_id=session_id,
            current_task="[TASK WILL BE INJECTED AT RUNTIME]",
            supervisor_name=supervisor_name,
            team_tool_report=team_tool_report_raw,
            conversation_history=my_history,
            tool_names=tool_names,
        )
    except Exception as e:
        console.print(f"[bold red]❌ Failed to build prompt: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return

    # Display
    console.print("\n[bold yellow]" + "=" * 60 + "[/bold yellow]")
    console.print(f"[bold yellow] FULL SYSTEM PROMPT — {agent_name}[/bold yellow]")
    console.print(f"[bold yellow] Role: {target_node.dynamic_name or 'TBD'}  |  Type: {target_node.agent_type}[/bold yellow]")
    console.print("[bold yellow]" + "=" * 60 + "[/bold yellow]\n")
    console.print(full_prompt)

    console.print("\n[bold green]" + "=" * 60 + "[/bold green]")
    console.print(f"[bold green] ✅ Prompt length: {len(full_prompt)} chars | Tools: {len(tool_names)} | Subordinates: {len(target_node.children)}[/bold green]")
    console.print("[bold green]" + "=" * 60 + "[/bold green]\n")


def view_all_prompts(session_id: str):
    """
    Dump the full 9-section system prompt for EVERY agent in the tree.
    """
    from core.engine.prompt_builder import build_agent_prompt
    from core.memory.execution_memory import load_agent_history

    root = rebuild_tree_from_redis(session_id=session_id)
    if not root:
        console.print(f"[bold red]❌ No tree found for '{session_id}'.[/bold red]")
        return

    def _init(node):
        try:
            node.session_id = session_id
            node.initialize_agent()
        except Exception:
            pass
        for child in node.children:
            _init(child)
    _init(root)

    raw_tool_report = redis.get(f"tool_report:{session_id}")
    team_tool_report_raw: dict = {}
    if raw_tool_report:
        try:
            team_tool_report_raw = json.loads(raw_tool_report.decode("utf-8"))
        except Exception:
            pass

    def _dump_node(node):
        tool_names = [t.name for t in node.tools] if hasattr(node, "tools") and node.tools else []
        supervisor_name = node.parent.common_name if node.parent else "human"
        my_history = load_agent_history(session_id, node.common_name)

        console.print(f"\n[bold magenta]{'═' * 70}[/bold magenta]")
        console.print(f"[bold magenta] AGENT: {node.common_name}  |  Role: {node.dynamic_name or 'TBD'}  |  Type: {node.agent_type}[/bold magenta]")
        console.print(f"[bold magenta]{'═' * 70}[/bold magenta]\n")

        try:
            full_prompt = build_agent_prompt(
                agent_node=node,
                session_id=session_id,
                current_task="[TASK WILL BE INJECTED AT RUNTIME]",
                supervisor_name=supervisor_name,
                team_tool_report=team_tool_report_raw,
                conversation_history=my_history,
                tool_names=tool_names,
            )
            console.print(full_prompt)
            console.print(f"\n[dim]Prompt length: {len(full_prompt)} chars | Tools: {len(tool_names)} | Subordinates: {len(node.children)}[/dim]")
        except Exception as e:
            console.print(f"[red]⚠️  Failed to build prompt for {node.common_name}: {e}[/red]")

        for child in node.children:
            _dump_node(child)

    _dump_node(root)


if __name__ == "__main__":
    session = Prompt.ask("Enter session_id to view", default="linkedin-clone-001")

    choice = Prompt.ask(
        "What would you like to view?\n"
        "  [1] Global State JSON (LangneuralState)\n"
        "  [2] Chronological Execution History (Raw)\n"
        "  [3] 3-Tiered Decaying Memory (Long/Medium/Short all-in-one)\n"
        "  [4] Full LLM Context (System Prompt) — single agent\n"
        "  [5] Full LLM Context (System Prompt) — ALL agents\n"
        "Choose",
        choices=["1", "2", "3", "4", "5"],
        default="3",
        show_choices=False
    )
    if choice == "1":
        view_state(session)
    elif choice == "2":
        view_history(session)
    elif choice == "3":
        view_tiered_memory(session)
    elif choice == "4":
        view_llm_context(session)
    elif choice == "5":
        view_all_prompts(session)
