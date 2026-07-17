from typing import List, Optional
from pydantic import BaseModel, Field
from ..agents.agent_node import AgentNode
from ..engine.llm_gateway import StructuredChatClient

class DynamicAgentSchema(BaseModel):
    common_name: str = Field(description="Unique internal ID like 'neuron_1'")
    dynamic_name: str = Field(description="Role name like 'backend_developer'")
    responsibility_domain: str = Field(description="What this agent owns and is accountable for.")
    subtask: str = Field(description="The specific instruction for this agent. For writers, append namespace restriction.")
    agent_type: str = Field(description="Must be 'writer', 'runner', or 'assembler'")
    build_stage: int = Field(description="Execution order: 0=producer, 1=consumer, 2=integrator")
    parent_common_name: Optional[str] = Field(description="The common_name of the manager this agent reports to. If null, this is the root agent.")

class DynamicOrgSchema(BaseModel):
    agents: List[DynamicAgentSchema] = Field(description="List of all agents in the organization.")

class DynamicOrgBuilder:
    """
    Builds a dynamic organizational hierarchy based on user intent.
    """
    def __init__(self):
        self.llm = StructuredChatClient()

    async def build_org(self, user_intent: str, session_id: str) -> AgentNode:
        system_prompt = """You are a Master Architect designing an Autonomous Organization.
Given a user's intent, design the perfect team of AI agents to accomplish the goal.
The framework is domain-agnostic. It can be for software, research, marketing, data pipelines, etc.

RULES:
1. Create a root supervisor agent (manager) with parent_common_name=null.
2. Create child agents reporting to the supervisor, or multiple tiers if complex.
3. Assign responsibility_domain to each.
4. Classify each agent into one of three types:
   - writer: Creates files in isolated namespace. Provide a directory path in their subtask.
   - runner: Executes commands (npm, docker, pytest, curl, python). No directory restriction.
   - assembler: Reads team output and writes ONE final file.
5. Assign build_stage (0=producers, 1=consumers, 2=integrators).
"""
        response = await self.llm.get_response(
            user_prompt=f"User Intent: {user_intent}",
            system_prompt=system_prompt,
            response_model=DynamicOrgSchema
        )

        # Convert to AgentNode tree
        node_map = {}
        root_node = None

        for spec in response.agents:
            node = AgentNode(
                common_name=spec.common_name,
                assigned_name=spec.dynamic_name,
                session_id=session_id
            )
            node.responsibility_domain = spec.responsibility_domain
            node.subtask_provided = spec.subtask
            node.set_agent_type(spec.agent_type)
            node.execution_stage = spec.build_stage
            
            node_map[spec.common_name] = {"node": node, "parent_name": spec.parent_common_name}

            if spec.parent_common_name is None:
                if root_node is not None:
                    print("⚠️ Warning: Multiple root nodes specified. Using the first one.")
                else:
                    root_node = node

        # Link parents and children
        for key, data in node_map.items():
            parent_name = data["parent_name"]
            if parent_name and parent_name in node_map:
                parent_node = node_map[parent_name]["node"]
                parent_node.children.append(data["node"])
                data["node"].parent = parent_node

        if not root_node:
            raise ValueError("LLM failed to generate a root node (parent_common_name=null).")

        return root_node
