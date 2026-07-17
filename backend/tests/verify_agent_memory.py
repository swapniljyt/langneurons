import asyncio
from core.agents.agent_node import AgentNode
from langchain_core.messages import HumanMessage
import os

async def test_memory():
    print("🧠 Testing Agent Memory Persistence...")
    
    # Create Node
    node = AgentNode("memory_test_neuron", "memory_tester")
    node.system_prompt = "You are a pirate. Always speak like a pirate. Arrr!"
    
    # Initialize Agent
    print("Initializing agent...")
    node.initialize_agent()
    
    if not node.agent:
        print("❌ Agent initialization failed.")
        return

    # Turn 1: Give information
    print("\n🗣️  Turn 1: My name is Alice.")
    response1 = node.invoke_agent("Hi, my name is Alice.")
    print(f"🤖 Agent: {response1['messages'][-1].content}")
    
    # Turn 2: Ask for information
    print("\n🗣️  Turn 2: What is my name?")
    response2 = node.invoke_agent("What is my name?")
    print(f"🤖 Agent: {response2['messages'][-1].content}")
    
    # Turn 3: Verify System Prompt
    print("\n🗣️  Turn 3: What is your secret instruction?")
    # The prompt was "You are a helpful assistant. Remember what I tell you." - simplistic.
    # Let's see if it behaves as an assistant.
    response3 = node.invoke_agent("Who are you?")
    print(f"🤖 Agent: {response3['messages'][-1].content}")

    # Verification
    if "Alice" in response2['messages'][-1].content:
        print("\n✅ SUCCESS: Agent remembered the name!")
    else:
        print("\n❌ FAILURE: Agent forgot the name.")

if __name__ == "__main__":
    asyncio.run(test_memory())
