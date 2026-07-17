"""
Rebuild the agent tree from Redis persistence.
This dynamically reconstructs the tree structure based on saved parent-child relationships.
"""
import json
import sys
import os
# Ensure the parent directory is in the Python path to import 'core'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.agents.agent_node import AgentNode, redis_client
from rich.console import Console

console = Console()

def rebuild_tree_from_redis(session_id: str = "default") -> AgentNode:
    """
    Rebuild the entire agent tree from Redis by reconstructing parent-child relationships.
    Returns the root node.
    """
    # Get all neuron keys from Redis for the current session
    neuron_keys = redis_client.keys(f"neuron:{session_id}:*")
    
    if not neuron_keys:
        console.print("[bold red]❌ No neurons found in Redis![/bold red]")
        return None
    
    # Create a dict to store all neurons by their common_name
    neurons_dict = {}
    
    # First, create all neuron objects
    for key in neuron_keys:
        data = redis_client.get(key)
        if data:
            neuron_data = json.loads(data.decode('utf-8'))
            common_name = neuron_data.get('common_name')
            
            # Create neuron object
            from core.skills.skill import Skill
            neuron = AgentNode(common_name=common_name, session_id=session_id)
            neuron.dynamic_name = neuron_data.get('dynamic_name', '')
            neuron.subtask_provided = neuron_data.get('subtask_provided', '')
            neuron.original_task = neuron_data.get('original_task', '')
            neuron.system_prompt = neuron_data.get('system_prompt', '')
            neuron.activate_flag = neuron_data.get('activate_flag', True)
            neuron.execution_stage = neuron_data.get('execution_stage', 0)
            neuron.module_name = neuron_data.get('module_name', '')
            neuron.agent_type = neuron_data.get('agent_type', 'writer')
            neuron._agent_type_manually_set = neuron_data.get('_agent_type_manually_set', False)
            
            # Reconstruct skills
            skills_data = neuron_data.get('skills', [])
            for sd in skills_data:
                neuron.add_skill(Skill(**sd))
            
            neurons_dict[common_name] = neuron
    
    # Second, reconstruct parent-child relationships
    root_neuron = None
    for key in neuron_keys:
        data = redis_client.get(key)
        if data:
            neuron_data = json.loads(data.decode('utf-8'))
            common_name = neuron_data.get('common_name')
            parent_name = neuron_data.get('parent_common_name')
            
            neuron = neurons_dict[common_name]
            
            if parent_name and parent_name in neurons_dict:
                # Set parent relationship
                parent = neurons_dict[parent_name]
                neuron.parent = parent
                parent.children.append(neuron)
            else:
                # This is the root neuron
                root_neuron = neuron
    
    console.print(f"[bold green]✅ Rebuilt tree with {len(neurons_dict)} neurons from Redis[/bold green]")
    return root_neuron

if __name__ == "__main__":
    root = rebuild_tree_from_redis()
    if root:
        console.print(f"\n[bold cyan]Root: {root.common_name} ({root.dynamic_name})[/bold cyan]")
        console.print(f"[bold cyan]Total children: {len(root.children)}[/bold cyan]")
