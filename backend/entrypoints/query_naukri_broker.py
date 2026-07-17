import sys, os
import asyncio
import json

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from core.swarm import rebuild_tree_from_redis, set_global_thinking, neural_agent
from core.state.langneural_state import LangneuralState, AgentNode as StateAgentNode, AgentExecutionRecord, AssignedTask
from core.memory.execution_memory import load_tool_report, persist_turn, persist_tool_report

SESSION_NAME = "naukri_job_broker_session"

async def run_query(user_query: str):
    root = rebuild_tree_from_redis(session_id=SESSION_NAME)
    if not root:
        print("Error: Swarm tree not initialized. Run entrypoints/run_naukri_broker.py first.")
        return

    # Initialize agents
    def _restore(node):
        node.session_id = SESSION_NAME
        node.initialize_agent()
        for child in node.children:
            _restore(child)
    _restore(root)

    # Build agent tools & hierarchy maps
    def _extract_tools(node) -> dict:
        tools_map = {}
        tool_names = [t.name for t in node.tools] if hasattr(node, "tools") and node.tools else []
        tools_map[node.common_name] = tool_names
        for child in node.children:
            tools_map.update(_extract_tools(child))
        return tools_map

    def _extract_hierarchy(node) -> dict:
        hierarchy_map = {}
        hierarchy_map[node.common_name] = StateAgentNode(
            supervisor=node.parent.common_name if node.parent else "human",
            subordinates=[child.common_name for child in node.children],
        )
        for child in node.children:
            hierarchy_map.update(_extract_hierarchy(child))
        return hierarchy_map

    agent_tools_map = _extract_tools(root)
    agent_hierarchy_map = _extract_hierarchy(root)
    global_team_tool_report = load_tool_report(SESSION_NAME) or {}

    state = LangneuralState(
        human_prompt=user_query,
        agent_tools=agent_tools_map,
        agent_hierarchy=agent_hierarchy_map,
        team_tool_report=global_team_tool_report,
    )

    state.team_execution_report[root.common_name] = AgentExecutionRecord(
        task_received=AssignedTask(
            supervisor="human",
            task_instructions=user_query,
            response_provided="pending",
        )
    )

    state = await neural_agent(
        agent_name=root.common_name,
        state=state,
        session_id=SESSION_NAME,
        root_node=root,
    )

    root_record = state.team_execution_report.get(root.common_name)
    final_response = (
        root_record.task_received.response_provided
        if root_record and root_record.task_received
        else "(No response generated)"
    )

    persist_turn(SESSION_NAME, state.team_execution_report)
    persist_tool_report(SESSION_NAME, state.team_tool_report)

    # Output ONLY the final response so it can be parsed by Node JS
    print(final_response)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python query_naukri_broker.py '<query>'")
        sys.exit(1)
    asyncio.run(run_query(sys.argv[1]))
