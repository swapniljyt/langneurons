import asyncio
import sys
import os

# Ensure the parent directory is in the Python path to import 'core'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from core.agents.agent_node import AgentNode
from rebuild_tree import rebuild_tree_from_redis

console = Console()

def traverse_and_load(node: AgentNode):
    """Recursively load roles and initialize agents for the tree."""
    node.load_role_from_redis()
    try:
        node.initialize_agent() 
    except Exception as e:
        console.print(f"[red]Failed to init agent for {node.common_name}: {e}[/red]")

    for child in node.children:
        traverse_and_load(child)

def find_node(root: AgentNode, name: str):
    return root.find_neuron_by_name(name)

async def chat_loop(node: AgentNode):
    """Interactive chat loop with the selected neuron."""
    console.print(f"\n[bold green]🗣️  Starting chat with {node.common_name} ({node.dynamic_name})[/bold green]")
    console.print("[dim]Type 'exit' to end the conversation.[/dim]\n")
    
    while True:
        # Get user input
        user_input = console.input("[bold cyan]You:[/bold cyan] ")
        
        # Check for exit
        if user_input.strip().lower() == "exit":
            console.print("\n[bold yellow]👋 Ending conversation. Goodbye![/bold yellow]")
            break
        
        if not user_input.strip():
            continue
        
        # Invoke the agent
        try:
            response = node.invoke_agent(user_input)
            agent_message = response['messages'][-1].content
            
            # Display response in a panel
            panel = Panel(
                agent_message,
                title=f"🤖 {node.dynamic_name}",
                border_style="green",
                padding=(1, 2)
            )
            console.print(panel)
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

async def main():
    if len(sys.argv) < 2:
        console.print("[bold red]Usage: python chat_with_neuron.py <neuron_name> [session_id][/bold red]")
        console.print("Example: python chat_with_neuron.py CasualMidWorkflowAgent hr_session")
        return
    
    target_name = sys.argv[1]
    session_id = sys.argv[2] if len(sys.argv) > 2 else "default"

    console.print(f"[bold yellow]🏗️  Rebuilding Agent Tree from Redis (Session: {session_id})...[/bold yellow]")
    root = rebuild_tree_from_redis(session_id=session_id)
    
    if root is None:
        console.print("[bold red]❌ Cannot chat because the tree is empty. Please run test.py first to generate the tree and populate Redis.[/bold red]")
        return
    
    console.print("[bold yellow]🔄 Restoring Roles & Initializing Agents from Redis...[/bold yellow]")
    traverse_and_load(root)
    console.print("[bold green]✅ Tree Ready.[/bold green]")
    
    # Find the neuron
    node = find_node(root, target_name)
    
    if not node:
        console.print(f"[bold red]❌ Neuron '{target_name}' not found in the tree.[/bold red]")
        return
    
    # Display neuron info
    info_panel = Panel(
        Text.assemble(
            ("Common Name: ", "bold cyan"), (f"{node.common_name}\n"),
            ("Dynamic Name: ", "bold magenta"), (f"{node.dynamic_name}\n"),
            ("Agent Type: ", "bold green"), (f"{type(node.agent)}\n" if node.agent else "None\n"),
            ("\nSystem Prompt:\n", "bold yellow"),
            (node.system_prompt if node.system_prompt else "[No system prompt set]", "white")
        ),
        title=f"🧠 Neuron Info: {node.common_name}",
        border_style="blue"
    )
    console.print(info_panel)
    
    if not node.agent:
        console.print("[bold red]❌ Agent not initialized. Cannot chat.[/bold red]")
        return
    
    # Start chat loop
    await chat_loop(node)

if __name__ == "__main__":
    asyncio.run(main())
