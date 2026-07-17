import asyncio
from langchain_core.tools import tool
from core.agents.agent_node import AgentNode
from core.engine.agent_factory import AgentFactory

# 1. Define the Tool
@tool
def write_code_to_file(file_path: str, content: str):
    """
    Writes the provided content to a file at the specified file_path.
    Use this tool to create or overwrite code files.
    """
    try:
        with open(file_path, "w") as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

async def main():
    print("🚀 Initializing Code Writer Agent...")

    # 2. Create a standard AgentNode
    node = AgentNode("coder_neuron", "senior_python_developer")
    
    # 3. Set a System Prompt instructing it to use the tool
    node.system_prompt = (
        "You are a Senior Python Developer. "
        "Your task is to write high-quality, executable Python code. "
        "ALWAYS use the 'write_code_to_file' tool to save your code to disk."
    )

    # 4. Initialize the Agent WITH the tool
    # Check if tools list is supported by your Factory
    tools = [write_code_to_file]
    
    # Using the factory directly or via node wrapper
    # Note: AgentNode.initialize_agent calls AgentFactory.create_agent
    node.initialize_agent(tools=tools)

    if not node.agent:
        print("❌ Agent failed to initialize.")
        return

    # 5. Define the target file and task
    target_file = "/home/swapniljyot/snaptron-git/synaptron_agents/test.py"
    task_description = (
        f"Please write a complete Python script to {target_file}. "
        "The script should print 'Hello from LangGraph Agent!' and define a function called 'greet'."
    )

    print(f"\n📝 Sending task: {task_description}")
    
    # 6. Run the Agent
    # We use the node's helper method if available, or invoke directly
    # Note: Using invoke_agent which supports thread_id memory
    response = node.invoke_agent(task_description)
    
    print("\n🤖 Agent Response:")
    print(response['messages'][-1].content)
    
    print("\n✅ Verifying file content:")
    try:
        with open(target_file, "r") as f:
            print(f"---\n{f.read()}\n---")
    except FileNotFoundError:
        print("❌ File was not created.")

if __name__ == "__main__":
    asyncio.run(main())
