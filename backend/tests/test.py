import asyncio
import time
from rich.console import Console
from collections import deque

from core.agents.agent_node import AgentNode
from core.agents.visualizer import Visualizer
from core.engine.orchestrator import Orchestrator

console = Console()

# -------------------------------
# Build Tree Structure
# -------------------------------
def build_test_tree() -> AgentNode:
    # Depth 0 (Root)
    root = AgentNode("root_neuron", "master")

    # Depth 1 children
    parentA = AgentNode("neuron_1", "slave1")
    parentB = AgentNode("neuron_2", "slave2")
    root.add_child(parentA)
    root.add_child(parentB)

    # Depth 2 children
    childA1 = AgentNode("neuron_3", "slave3")
    childA2 = AgentNode("neuron_4", "slave4")
    parentA.add_child(childA1)
    parentA.add_child(childA2)

    childB1 = AgentNode("neuron_5", "slave5")
    childB2 = AgentNode("neuron_6", "slave6")
    parentB.add_child(childB1)
    parentB.add_child(childB2)

    # Depth 3 children for A1
    childA1.add_child(AgentNode("neuron_7", "slave7"))
    childA1.add_child(AgentNode("neuron_8", "slave8"))

    # Depth 3 children for A2
    childA2.add_child(AgentNode("neuron_9", "slave9"))
    childA2.add_child(AgentNode("neuron_10", "slave10"))

    # Depth 3 children for B1
    childB1.add_child(AgentNode("neuron_11", "slave11"))
    childB1.add_child(AgentNode("neuron_12", "slave12"))

    # Depth 3 children for B2
    childB2.add_child(AgentNode("neuron_13", "slave13"))
    childB2.add_child(AgentNode("neuron_14", "slave14"))

    return root


# -------------------------------
# Run Task Split + Visualize
# -------------------------------
async def main():
    root = build_test_tree()
    
    # Save task metadata to Redis so inspect_neuron.py can rebuild the correct tree
    from core.agents.agent_node import redis_client
    import json
    
    original_task = "please make a snapchat app for me"
    
    # Count total neurons in the tree
    def count_neurons(node):
        count = 1
        for child in node.children:
            count += count_neurons(child)
        return count
    
    neuron_count = count_neurons(root)
    
    task_metadata = {
        "task": original_task,
        "neuron_count": neuron_count
    }
    redis_client.set("last_task", json.dumps(task_metadata))
    console.print(f"[dim]💾 Saved task metadata: {neuron_count} neurons, task: '{original_task}'[/dim]\n")
    
    # Initialize the New Brain (Orchestrator)
    # freeze_mode=False (unfreeze) = orchestration building mode, rebuilds tree from scratch
    cerebrum = Orchestrator(freeze_mode=False)
    visual_cortex = Visualizer()

    start_time = time.time()

    await cerebrum.start_reaction(
        original_task=original_task,
        root=root
    )

    end_time = time.time()

    console.rule("[bold green]🎉 Pipeline Finished[/bold green]")
    console.print(f"[bold green]Total time: {end_time - start_time:.2f}s[/bold green]\n")

    # Save the complete tree to Redis so chat_with_neuron.py can rebuild it
    AgentNode.save_tree_to_redis(root)
    console.print(f"[dim]💾 Saved complete neuron tree to Redis[/dim]\n")

    # Full tree
    console.rule("[bold cyan]🌳 Final Neuron Tree[/bold cyan]")
    visual_cortex.print_tree_with_stats(root)

if __name__ == "__main__":
    asyncio.run(main())
