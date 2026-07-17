import asyncio
from core.agents.agent_node import AgentNode, redis_client
import json

async def test_conversation_persistence():
    print("🧪 Testing Conversation Persistence to Redis...\n")
    
    # Create a test neuron
    node = AgentNode("test_memory_neuron", "memory_tester")
    node.system_prompt = "You are a helpful assistant."
    node.initialize_agent()
    
    # Have a short conversation
    print("Turn 1:")
    response1 = node.invoke_agent("My name is Alice")
    print(f"Agent: {response1['messages'][-1].content}\n")
    
    print("Turn 2:")
    response2 = node.invoke_agent("What's my name?")
    print(f"Agent: {response2['messages'][-1].content}\n")
    
    # Check Redis
    conversation_key = f"conversation:{node.common_name}"
    conversation_data = redis_client.get(conversation_key)
    
    if conversation_data:
        conversation_history = json.loads(conversation_data.decode('utf-8'))
        print(f"✅ SUCCESS: {len(conversation_history)} messages stored in Redis")
        print("\nStored conversation:")
        for i, msg in enumerate(conversation_history[-4:], 1):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')[:60]
            print(f"  {i}. [{role}]: {content}...")
    else:
        print("❌ FAIL: No conversation data found in Redis")

if __name__ == "__main__":
    asyncio.run(test_conversation_persistence())
