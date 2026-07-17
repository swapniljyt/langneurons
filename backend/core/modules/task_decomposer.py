from json import dumps
from typing import List, Dict, Type, TypeVar
from pydantic import BaseModel

from ..engine.llm_gateway import StructuredChatClient
from ..utils.multithreading import executor
from ..utils.prompt_loader import PromptLoader

T = TypeVar("T", bound=BaseModel)

class SubTask_by_name(BaseModel):
    common_name: str
    dynamic_name: str
    responsibility_domain: str = "" # Full ownership context (e.g. "You own the landing experience...")
    subtask: str
    build_stage: int = 0  # Execution order: 0=producers, 1=consumers, 2=integrators
    agent_type: str = "writer"  # Domain-agnostic classification:
                                #   "writer"    — creates source files (gets isolated namespace)
                                #   "runner"    — executes commands only (no namespace restriction)
                                #   "assembler" — reads all team output, writes ONE final file


class ContextualDivideAndConquerResponse(BaseModel):
    original_task: str
    parent_task: str
    subtasks: List[SubTask_by_name]

class NonContextualDivideAndConquerResponse(BaseModel):
    original_task: str
    parent_task: str
    subtasks: List[SubTask_by_name]

class TaskDecomposer:
    """
    Task Decomposer & Planning Unit
    Responsible for breaking down complex tasks into subtasks for neurons.
    """
    def __init__(self, llm_client: StructuredChatClient):
        self.llm_client = llm_client

    async def async_contextual_decompose_task(
        self,
        original_task: str,
        parent_task: str,
        neurons_dict: Dict[str, str],
        context,
        parent_role: str = "Root Manager"
    ) -> ContextualDivideAndConquerResponse:

        system_prompt = PromptLoader.get_prompt(
            "system/task_decomposition_contextual.md",
            len_neurons_dict=len(neurons_dict),
            neurons_dict_dump=dumps(neurons_dict, indent=2),
            original_task=original_task,
            parent_task=parent_task,
            parent_role=parent_role
        )

        user_content = f"""
TASK TO DECOMPOSE:
original_task: {original_task}
parent_task: {parent_task}
parent_role: {parent_role}

NEURONS AVAILABLE:
{dumps(neurons_dict, indent=2)}

CONTEXT:
{context}

Create exactly {len(neurons_dict)} subtasks using the neurons provided above.
"""

        return await self.llm_client.get_response(
            system_prompt=system_prompt,
            user_prompt=user_content,
            response_model=ContextualDivideAndConquerResponse
        )

    async def async_non_contextual_decompose_task(
        self,
        original_task: str,
        parent_task: str,
        neurons_dict: Dict[str, str],
        parent_role: str = "Root Manager"
    ) -> NonContextualDivideAndConquerResponse:

        system_prompt = PromptLoader.get_prompt(
            "system/task_decomposition_non_contextual.md",
            len_neurons_dict=len(neurons_dict),
            neurons_dict_dump=dumps(neurons_dict, indent=2),
            original_task=original_task,
            parent_task=parent_task,
            parent_role=parent_role
        )

        user_content = f"""
DECOMPOSE THIS TASK:
original_task: {original_task}
parent_task: {parent_task}
parent_role: {parent_role}

USE THESE NEURONS EXACTLY:
{dumps(neurons_dict, indent=2)}

Output: Create {len(neurons_dict)} subtasks in JSON format using the neurons above.
"""

        return await self.llm_client.get_response(
            system_prompt=system_prompt,
            user_prompt=user_content,
            response_model=NonContextualDivideAndConquerResponse
        )
