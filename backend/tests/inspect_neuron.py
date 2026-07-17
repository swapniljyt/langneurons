import asyncio
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from core.agents.agent_node import AgentNode
from test_2 import build_large_tree

console = Console()

def traverse_and_load(node: AgentNode):
    """Recursively load roles and initialize agents for the tree."""
    # Load persistence
    node.load_role_from_redis()
    
    # Initialize agent (this creates the LangGraph app/chain based on System Prompt)
    # We do this to see "which agent it has been used" (the object type)
    try:
        node.initialize_agent() 
    except Exception as e:
        console.print(f"[red]Failed to init agent for {node.common_name}: {e}[/red]")

    for child in node.children:
        traverse_and_load(child)

def find_node(root: AgentNode, name: str):
    return root.find_neuron_by_name(name)

async def main():
    if len(sys.argv) < 2:
        console.print("[bold red]Usage: python inspect_neuron.py <neuron_name_or_all>[/bold red]")
        console.print("Using 'all' will list all active neurons.")
        target_name = "all"
    else:
        target_name = sys.argv[1]

    # Get the last task from Redis to rebuild the tree dynamically
    from core.agents.agent_node import redis_client
    import json
    
    last_task_key = "last_task"
    last_task_data = redis_client.get(last_task_key)
    
    if not last_task_data:
        console.print("[bold red]❌ No task found in Redis. Run test.py first![/bold red]")
        console.print("[yellow]Falling back to 10-neuron tree...[/yellow]")
        root = build_large_tree(10, 3)
    else:
        # Parse the last task and rebuild the tree
        task_info = json.loads(last_task_data.decode('utf-8'))
        original_task = task_info.get('task', 'default task')
        neuron_count = task_info.get('neuron_count', 10)
        
        console.print(f"[bold yellow]🏗️  Rebuilding Agent Tree ({neuron_count} Neurons) for task: '{original_task}'...[/bold yellow]")
        root = build_large_tree(neuron_count, 3)
    
    console.print("[bold yellow]🔄 Restoring Roles & Initializing Agents from Redis...[/bold yellow]")
    traverse_and_load(root)
    console.print("[bold green]✅ Tree Ready.[/bold green]")
    console.print()

    if target_name.lower() == "all":
        # List all neurons that have a specific role (not default slave_X) OR all of them
        table = Table(title="All Neurons Status")
        table.add_column("Common Name", style="cyan")
        table.add_column("Dynamic Name", style="magenta")
        table.add_column("Agent Type", style="green")
        table.add_column("Has Prompt?", style="yellow")

        nodes_to_visit = [root]
        while nodes_to_visit:
            curr = nodes_to_visit.pop(0)
            
            agent_type = type(curr.agent).__name__ if curr.agent else "None"
            has_prompt = "✅ Yes" if curr.system_prompt else "❌ No"
            
            table.add_row(curr.common_name, curr.dynamic_name, agent_type, has_prompt)
            nodes_to_visit.extend(curr.children)
        
        console.print(table)
        return

    # Specific Neuron Search
    node = find_node(root, target_name)
    
    if not node:
        console.print(f"[bold red]❌ Neuron '{target_name}' not found in the tree.[/bold red]")
        return
    
    # Display Details
    # Load conversation history from Redis if available
    from core.agents.agent_node import redis_client
    import json
    
    conversation_key = f"conversation:{node.common_name}"
    conversation_data = redis_client.get(conversation_key)
    
    if conversation_data:
        conversation_history = json.loads(conversation_data.decode('utf-8'))
        context_display = f"{len(conversation_history)} messages stored (last 23)"
    else:
        context_display = "0 entries stored"
    
    p = Panel(
        Text.assemble(
            ("Common Name: ", "bold cyan"), (f"{node.common_name}\n"),
            ("Dynamic Name: ", "bold magenta"), (f"{node.dynamic_name}\n"),
            ("Agent Type:  ", "bold green"), (f"{type(node.agent)}\n" if node.agent else "None\n"),
            ("Conversation History:", "dim"), (f" {context_display}\n"),
            ("\nSystem Prompt:\n", "bold yellow"),
            (node.system_prompt if node.system_prompt else "[No system prompt set]", "white")
        ),
        title=f"🧠 Neuron Inspection: {node.common_name}",
        border_style="blue"
    )
    console.print(p)
    
    # Show last few conversation turns if available
    if conversation_data:
        console.print("\n[bold cyan]📜 Recent Conversation (last 5 messages):[/bold cyan]")
        recent = conversation_history[-5:]
        for msg in recent:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if role == 'human':
                console.print(f"[bold green]👤 User:[/bold green] {content[:100]}...")
            elif role == 'ai':
                console.print(f"[bold blue]🤖 Agent:[/bold blue] {content[:100]}...")
        console.print()

    if node.agent:
        console.print("[dim]Agent object is ready for execution.[/dim]")

if __name__ == "__main__":
    asyncio.run(main())

#run  these two commands
#python inspect_neuron.py all
#python inspect_neuron.py neuron_1