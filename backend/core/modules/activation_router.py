from json import dumps
from typing import List, Type, TypeVar
from pydantic import BaseModel

from ..engine.llm_gateway import StructuredChatClient
from ..utils.prompt_loader import PromptLoader

T = TypeVar("T", bound=BaseModel)

class CommonDynamicName(BaseModel):
    common_name: str
    dynamic_name: str

class ActivatedNeurons(BaseModel):
    Fired_Neurons: List[CommonDynamicName]
    context_flag: bool

class ActivationRouter:
    """
    Attention & Activation System
    Responsible for selecting and activating appropriate neurons for a task.
    """
    def __init__(self, llm_client: StructuredChatClient):
        self.llm_client = llm_client

    async def _fired_neurons_selection(self, original_task: str, neurons_roles: List[dict], neural_schema: str) -> ActivatedNeurons:
        """Select existing neurons whose roles match the current task."""
        
        system_prompt = PromptLoader.get_prompt("system/activation.md")
        schema_prompt = PromptLoader.get_prompt("system/neural_schema.md").replace("{{NEURAL_SCHEMA}}", neural_schema)
        
        # Merge system prompts or append schema to user content
        # Appending to system prompt is cleaner
        full_system_prompt = f"{system_prompt}\n\n{schema_prompt}"
        
        user_content = f"""
        *TASK*: {original_task}
        
        AVAILABLE NEURONS AND THEIR CURRENT ROLES:
        {dumps(neurons_roles, indent=2)}
        
        INSTRUCTIONS:
        1. Select neurons whose current roles match this subtask
        2. Copy their names EXACTLY as shown above
        3. Return in the required JSON format
        
        YOUR SELECTION:"""
        
        return await self.llm_client.get_response(
            system_prompt=full_system_prompt,
            user_prompt=user_content,
            response_model=ActivatedNeurons
        )

    async def _create_new_neurons_assignment(self, realtime_subtask: str, neurons_roles: List[dict], neural_schema: str) -> ActivatedNeurons:
        """Create new neuron role assignments for a new task."""
        
        system_prompt = PromptLoader.get_prompt("system/activation_new_task.md")
        schema_prompt = PromptLoader.get_prompt("system/neural_schema.md").replace("{{NEURAL_SCHEMA}}", neural_schema)
        
        full_system_prompt = f"{system_prompt}\n\n{schema_prompt}"

        neuron_ids = list(neurons_roles.keys())
        user_content = f"""
        CURRENT SUBTASK: {realtime_subtask}
        
        AVAILABLE NEURON IDs (use these EXACTLY): {neuron_ids}
        
        INSTRUCTIONS:
        1. Divide this subtask into {len(neuron_ids)} EQUAL parts
        2. Assign each neuron ID to one part
        3. Create role names that show the division
        4. Return in required JSON format
        
        IMPORTANT: You MUST use ALL {len(neuron_ids)} neuron IDs provided above.
        
        YOUR ASSIGNMENT:"""

        return await self.llm_client.get_response(
            system_prompt=full_system_prompt,
            user_prompt=user_content,
            response_model=ActivatedNeurons
        )

    async def activate_neurons(self, neurons_roles: List[dict], context_flag: bool, realtime_subtask: str, original_task: str, neural_schema: str) -> ActivatedNeurons:
        """
        Activates neurons based on context matching and task requirements.
        """
        if context_flag:
            print("===context match sucessfully===")
            activation = await self._fired_neurons_selection(original_task, neurons_roles, neural_schema)
            activation.context_flag = True
            return activation
        else:
            print("===context not match===")
            activation = await self._create_new_neurons_assignment(
                realtime_subtask, neurons_roles, neural_schema
            )
            activation.context_flag = False
            return activation
