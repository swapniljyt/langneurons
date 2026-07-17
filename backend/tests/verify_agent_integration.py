from core.agents.agent_node import AgentNode
from langchain_core.messages import HumanMessage
import asyncio
import os

# Set dummy key if missing, but we assume environment is set
if not os.getenv("OPENAI_API_KEY"):
    print("Warning: OPENAI_API_KEY not set. Test might fail.")

async def verify_agent_execution():
    print("🧪 Verifying AgentNode execution...")
    
    # Create a node
    node = AgentNode("test_neuron", "test_role")
    node.system_prompt = "You are a helpful assistant that answers with 'Success'."
    
    # Initialize agent
    print("Initializing agent...")
    try:
        node.initialize_agent()
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return

    if node.agent:
        print(f"✅ Agent initialized: {type(node.agent)}")
        
        # Test Reference - invoke it (simulated)
        # Since it's a compiled graph or chain, we can invoke it.
        # But without a real key/mock, we can't make a real API call easily without cost/time.
        # But we can check if it has the .invoke method.
        if hasattr(node.agent, "invoke") or hasattr(node.agent, "ainvoke"):
            print("✅ Agent has invoke method.")
        else:
            print("❌ Agent missing invoke method.")
    else:
        print("❌ Agent is None.")

if __name__ == "__main__":
    asyncio.run(verify_agent_execution())
