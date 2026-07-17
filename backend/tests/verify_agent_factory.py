from core.engine.agent_factory import AgentFactory
from langchain_core.messages import HumanMessage
import os

# Set dummy key if not present for initialization check (won't run inference)
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "sk-dummy"

try:
    print("Testing AgentFactory with empty tools...")
    agent = AgentFactory.create_agent(system_prompt="You are a test agent.", tools=[])
    print("Successfully created agent with empty tools.")
    print(f"Agent type: {type(agent)}")
    
    # We won't invoke it because we might not have a real key or it might error on empty tools during execution
    # But creation success is a good first step.
    
except Exception as e:
    print(f"Failed to create agent: {e}")
    import traceback
    traceback.print_exc()
