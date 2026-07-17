from json import dumps
from typing import List, Dict, Type, TypeVar
from pydantic import BaseModel

from ..engine.llm_gateway import StructuredChatClient
from ..utils.multithreading import executor
from ..utils.prompt_loader import PromptLoader

T = TypeVar("T", bound=BaseModel)

class SystemPromptAssignerResponse(BaseModel):
    common_name: str
    system_prompt: str

class RoleManager:
    """
    Role & Identity System (System Prompt Assigner)
    Responsible for assigning detailed personas and roles to neurons.
    """
    def __init__(self, llm_client: StructuredChatClient):
        self.llm_client = llm_client

    async def assign_system_prompt(self,
        common_name: str,
        role: str,
        original_task: str,
        First_subtask_task: str,
        parent_info: dict = None,
        children_info: list = None,
        siblings_info: list = None,
        team_directory: list = None,
        custom_persona: str = None,
        agent_type: str = None
    ) -> SystemPromptAssignerResponse:
        
        # Build TEAM DIRECTORY section
        if isinstance(team_directory, list) and len(team_directory) > 0:
            team_dir_lines = "\n".join([f"- {agent['name']} — {agent['role']}" for agent in team_directory])
        elif isinstance(team_directory, str):
            team_dir_lines = team_directory
        else:
            team_dir_lines = "- (No team information available)"
        
        # Build BOSS section
        if parent_info:
            boss_info = f"- {parent_info['name']} ({parent_info['role']})\nYou must follow instructions from your boss and align your work accordingly."
        else:
            boss_info = "- None (You are a top-level coordinator)"
        
        # Collaborators section removed - using pure hierarchical structure (Boss -> Agent -> Subordinates)
        
        # Build SUBORDINATES section
        if children_info and len(children_info) > 0:
            subordinates_lines = "\n".join([f"- {c['name']} — {c['role']}" for c in children_info])
            subordinates_lines += "\nDelegate tasks and integrate their outputs."
        else:
            subordinates_lines = "- None (No junior agents under you)"
        
        # Handle custom persona instructions
        if custom_persona:
            user_content_suffix = (
                f"\n\nCRITICAL PERSONA INSTRUCTION: The user has pre-defined a strict identity "
                f"for this agent. You MUST use this exact text word-for-word as the PERSONA section:\n"
                f"\"{custom_persona}\"\n"
                f"Derive the agent's 3 RESPONSIBILITIES entirely from this custom persona — DO NOT "
                f"use the root task or subtask to infer responsibilities."
            )
        else:
            user_content_suffix = ""

        # Handle tool usage specifically for LEAF agents
        tool_usage_block = ""
        tool_instruction = ""
        from core.tools.registry import get_tool_names_for_agent
        if agent_type and (not children_info or len(children_info) == 0):
            available_tools = get_tool_names_for_agent(agent_type)
            if available_tools:
                tools_list_str = ", ".join(available_tools)
                tool_usage_block = f"\n━━━━━━━━━━━━━━━━━━━━\nTOOL USAGE\n━━━━━━━━━━━━━━━━━━━━\nYou have access to the following tools: {tools_list_str}.\n[Explain exactly when and how to use these tools for your specific subtask. Provide a brief map or strategy for tool execution.]\n"
                tool_instruction = f"7. TOOL USAGE: Since you are a leaf agent, generate a 'TOOL USAGE' section outlining exactly how to use your available tools ({tools_list_str}) to accomplish your subtask."

        # Load template — team directory, boss, subordinate info, and tool usage
        system_prompt_template = PromptLoader.get_prompt(
            "system/prompt_assignment.md", 
            common_name=common_name,
            team_directory=team_dir_lines,
            boss_info=boss_info,
            subordinates_info=subordinates_lines,
            user_instruction_block=tool_usage_block
        )
        
        user_content = f"""Role: {role}
Original Task: {original_task}
First Subtask: {First_subtask_task}{user_content_suffix}

Generate a structured system prompt following the template format EXACTLY.

REQUIREMENTS:
1. Use the role "{role}" as the agent name in the opening line
2. PERSONA: write 2-3 sentences describing personality, expertise and priorities for this role
3. TEAM DIRECTORY: already filled in the template — copy it exactly, do not modify
4. COMMAND HIERARCHY: already filled in the template — copy it exactly, do not modify
5. RESPONSIBILITIES: list exactly 3 numbered responsibilities relevant to this agent's role
6. EXECUTION RULES: copy from the template exactly
{tool_instruction}

Do NOT add extra sections. Do NOT include instruction text in the output.
"""

        return await self.llm_client.get_response(
            user_prompt=user_content,
            system_prompt=system_prompt_template,
            response_model=SystemPromptAssignerResponse
        )
