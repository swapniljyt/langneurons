import argparse
import asyncio
import json
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from rich.table import Table
from rich import print as rprint

from core.agents.agent_node import AgentNode
from core.tools.registry import get_tool_names_for_agent
from tests.rebuild_tree import rebuild_tree_from_redis

console = Console()

def find_neuron(node: AgentNode, target_name: str) -> AgentNode:
    """Recursively search for a neuron by common_name."""
    if node.common_name.lower() == target_name.lower():
        return node
    for child in node.children:
        found = find_neuron(child, target_name)
        if found:
            return found
    return None

def inspect_neuron(session_id: str, neuron_name: str):
    console.rule(f"[bold bright_cyan]🧠 INSPECTING NEURON: {neuron_name}[/bold bright_cyan]")
    
    with console.status(f"[dim]Loading session '{session_id}' from Redis...[/dim]"):
        root = rebuild_tree_from_redis(session_id=session_id)
        
    if not root:
        console.print(f"[bold red]❌ Could not load session '{session_id}' from Redis.[/bold red]")
        return
        
    neuron = find_neuron(root, neuron_name)
    if not neuron:
        console.print(f"[bold red]❌ Neuron '{neuron_name}' not found in session '{session_id}'.[/bold red]")
        return
        
    # Basic Identity
    identity_table = Table(show_header=False, box=None, padding=(0, 2))
    identity_table.add_column("Property", style="bold cyan")
    identity_table.add_column("Value", style="white")
    
    identity_table.add_row("Common Name", neuron.common_name)
    identity_table.add_row("Dynamic Role", getattr(neuron, 'dynamic_name', 'Unknown'))
    identity_table.add_row("Agent Type", getattr(neuron, 'agent_type', 'Unknown'))
    
    # Hierarchy
    boss = neuron.parent.common_name if neuron.parent else "None (Root)"
    subs = ", ".join([c.common_name for c in neuron.children]) if neuron.children else "None (Leaf)"
    identity_table.add_row("Boss (Assigned By)", boss)
    identity_table.add_row("Subordinates", subs)
    
    # Tools
    tools = get_tool_names_for_agent(getattr(neuron, 'agent_type', 'writer'))
    tools_str = ", ".join(tools) if tools else "None"
    identity_table.add_row("Assigned Tools", tools_str)
    
    console.print(Panel(identity_table, title="[bold green]Identity & Structure[/bold green]", border_style="green", expand=False))
    
    # Task Info
    task_table = Table(show_header=False, box=None, padding=(0, 2))
    task_table.add_column("Property", style="bold yellow")
    task_table.add_column("Value", style="white")
    task_table.add_row("Original Task", getattr(neuron, 'original_task', 'N/A'))
    task_table.add_row("Delegated Subtask", getattr(neuron, 'subtask_provided', 'N/A'))
    
    console.print(Panel(task_table, title="[bold yellow]Task Assignments[/bold yellow]", border_style="yellow", expand=False))
    
    # Skills
    if getattr(neuron, 'skills', None):
        skill_text = ""
        for i, skill in enumerate(neuron.skills):
            skill_text += f"[bold magenta]Skill {i+1}: {skill.name}[/bold magenta]\n"
            skill_text += f"[dim]Trigger:[/dim] {skill.start_trigger}\n"
            skill_text += f"[dim]Instructions:[/dim] {skill.instructions}\n"
            skill_text += f"[dim]End Condition:[/dim] {skill.end_condition}\n\n"
        console.print(Panel(skill_text.strip(), title="[bold magenta]Skills & Instructions[/bold magenta]", border_style="magenta", expand=False))
    else:
        console.print(Panel("[dim]No explicit skills assigned.[/dim]", title="[bold magenta]Skills & Instructions[/bold magenta]", border_style="magenta", expand=False))
        
    # System Prompt
    prompt = getattr(neuron, 'system_prompt', None)
    if prompt:
        # truncate slightly if too huge, but usually fine to print full
        console.print(Panel(prompt, title="[bold blue]Generated System Prompt[/bold blue]", border_style="blue", expand=False))
    else:
        console.print(Panel("[dim]No system prompt generated.[/dim]", title="[bold blue]Generated System Prompt[/bold blue]", border_style="blue", expand=False))
        
    # Context/Metadata from Redis
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0, password='testpass')
        state_data = r.get(f"neuron:{session_id}:{neuron.common_name}")
        if state_data:
            state = json.loads(state_data.decode('utf-8'))
            meta = state.get('agent_metadata', {})
            if meta:
                meta_str = json.dumps(meta, indent=2)
                console.print(Panel(meta_str, title="[bold cyan]Agent Metadata (State)[/bold cyan]", border_style="cyan", expand=False))
            else:
                console.print(Panel("[dim]No metadata currently set in state.[/dim]", title="[bold cyan]Agent Metadata (State)[/bold cyan]", border_style="cyan", expand=False))
    except Exception as e:
        console.print(f"[dim]Could not load runtime metadata: {e}[/dim]")

def main():
    parser = argparse.ArgumentParser(description="Inspect a specific neuron in the LangNeurons swarm.")
    parser.add_argument("neuron_name", help="The common_name of the neuron to inspect (e.g., RouterAgent)")
    parser.add_argument("--session", default="hr_auto_session", help="The session ID to load from Redis")
    
    args = parser.parse_args()
    inspect_neuron(args.session, args.neuron_name)

if __name__ == "__main__":
    main()
