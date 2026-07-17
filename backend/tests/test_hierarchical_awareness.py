import asyncio
import sys
import os
# Ensure the parent directory and tests directory are in the Python path
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.agents.agent_node import AgentNode
from core.engine.orchestrator import Orchestrator
from test_2 import build_large_tree

async def main():
    print("🧪 Testing Hierarchical Agentic Society Awareness...\n")
    
    # Build tree
    root = build_large_tree(10, 3)
    
    # Run orchestrator with depth=1 to assign roles and prompts
    orchestrator = Orchestrator()
    await orchestrator.start_reaction(
        original_task="please make a simple task manager app",
        root=root,
        depth=1
    )
    
    print("\n✅ Tree built with hierarchical awareness!")
    print("\nNow use: python inspect_neuron.py neuron_1")
    print("Or chat: python chat_with_neuron.py neuron_1")

if __name__ == "__main__":
    asyncio.run(main())
