import asyncio
import sys
import os
# Ensure the parent directory is in the Python path to import 'core'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import sys
from rich.console import Console
from core.agents.agent_node import AgentNode
from test_2 import build_large_tree

console = Console()

def traverse_and_load(node: AgentNode):
    """Recursively load roles and initialize agents for the tree."""
    # Only load if active (in our simple tree build, all created nodes are potentially active)
    # But let's check flag from Redis if possible? Or just load all.
    success = node.load_role_from_redis()
    
    if success:
        try:
            node.initialize_agent() 
            # Load context too, to get the subtask if not already set?
            # Actually subtask is stored in context, let's retrieve it if missing
            if not node.subtask_provided:
                context = node.get_context_from_redis()
                if context and len(context) > 0:
                    last_ctx = context[0]
                    node.subtask_provided = last_ctx.get("subtask_provided", "")
                    
        except Exception as e:
            console.print(f"[red]Failed to init agent for {node.common_name}: {e}[/red]")
    else:
        # If no role in Redis, maybe skip initialization?
        # But for test purposes, let's warn
        # console.print(f"[dim]No role found for {node.common_name}, skipping init.[/dim]")
        pass

    for child in node.children:
        traverse_and_load(child)

async def trigger_all_agents(root: AgentNode):
    """Iterate through all agents and invoke them with their subtask."""
    console.print("\n[bold cyan]🚀 Triggering Agent Execution Sequence...[/bold cyan]")
    
    agents_to_trigger = []
    
    def collect_agents(node):
        if node.agent and node.subtask_provided:
            agents_to_trigger.append(node)
        for child in node.children:
            collect_agents(child)
            
    collect_agents(root)
    
    console.print(f"[bold green]Found {len(agents_to_trigger)} ready agents.[/bold green]\n")
    
    for agent_node in agents_to_trigger:
        console.print(f"🎬 [bold yellow]Invoking {agent_node.common_name} ({agent_node.dynamic_name})...[/bold yellow]")
        console.print(f"   [dim]Subtask: {agent_node.subtask_provided[:60]}...[/dim]")
        
        try:
            # Run in executor to avoid blocking too much? invoke is sync or async? 
            # agent.invoke is usually sync in LangChain unless async method used.
            # But here we are in async loop. Let's wrap it or just call it.
            # If blocking, it will pause the loop, which is fine for a trigger script.
            
            response = agent_node.invoke_agent(agent_node.subtask_provided)
            content = response.get('messages', [])[-1].content
            console.print(f"   ✅ [green]Response received ({len(content)} chars)[/green]")
            
        except Exception as e:
            console.print(f"   ❌ [red]Error: {e}[/red]")
            
        console.print("-" * 40)
        # Small delay to mimic sequential propagation or avoiding rate limits
        await asyncio.sleep(1)

async def main():
    console.print("[bold yellow]🏗️  Rebuilding Agent Tree (10 Neurons)...[/bold yellow]")
    # Using same parameters as test.py usually does
    root = build_large_tree(10, 3)
    
    console.print("[bold yellow]🔄 Restoring Roles & Initializing Agents from Redis...[/bold yellow]")
    traverse_and_load(root)
    console.print("[bold green]✅ Tree Ready.[/bold green]")
    
    await trigger_all_agents(root)
    
    console.print("\n[bold green]✨ Execution Complete.[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
