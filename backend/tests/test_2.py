import asyncio
import time
from rich.console import Console
from collections import deque

from core.agents.agent_node import AgentNode
from core.agents.visualizer import Visualizer
from core.engine.orchestrator import Orchestrator

console = Console()

# -------------------------------
# Build Large Tree Structure (50 Neurons)
# -------------------------------
def build_large_tree(total_neurons=10, branching_factor=3) -> AgentNode:
    """
    Builds a balanced tree with exactly `total_neurons` nodes.
    """
    if total_neurons < 1:
        raise ValueError("Must have at least 1 neuron")

    # Create Root
    root = AgentNode("root_neuron", "master")
    created_count = 1
    
    # Queue for breadth-first addition
    # Stores tuples of (parent_neuron)
    queue = deque([root])
    
    neuron_index = 1
    
    while created_count < total_neurons and queue:
        parent = queue.popleft()
        
        # Add children to this parent
        for _ in range(branching_factor):
            if created_count >= total_neurons:
                break
                
            child_name = f"neuron_{neuron_index}"
            child = AgentNode(child_name, f"slave_{neuron_index}")
            parent.add_child(child)
            queue.append(child)
            
            created_count += 1
            neuron_index += 1
            
    return root

# -------------------------------
# Run Task Split + Visualize
# -------------------------------
async def main():
    console.print(f"[bold yellow]🏗️  Building Matrix with 10 Neurons...[/bold yellow]")
    root = build_large_tree(10, 3) # Branching factor 3
    
    # Initialize the New Brain (Orchestrator)
    # freeze_mode=False (unfreeze) = orchestration building mode, rebuilds tree from scratch
    cerebrum = Orchestrator(freeze_mode=False)
    visual_cortex = Visualizer()

    console.print(f"[bold green]✅ Matrix Initialized. Total Nodes: 10[/bold green]")
    start_time = time.time()

    await cerebrum.start_reaction(
        original_task="create a website for me please ",
        root=root   
    )

    end_time = time.time()

    console.rule("[bold green]🎉 Pipeline Finished[/bold green]")
    console.print(f"[bold green]Total time: {end_time - start_time:.2f}s[/bold green]\n")

    # Full tree
    console.rule("[bold cyan]🌳 Final Neuron Tree[/bold cyan]")
    visual_cortex.print_tree_with_stats(root)

if __name__ == "__main__":
    asyncio.run(main())
