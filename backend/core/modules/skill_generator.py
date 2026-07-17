"""
core/modules/skill_generator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generates the per-agent skill file, which IS the system prompt for that agent.

The skill file (saved as .md in core/skills/definitions/{session_id}/) contains:
  - PERSONA
  - TEAM DIRECTORY
  - COMMAND HIERARCHY
  - RESPONSIBILITIES
  - STRICT RULES & ROUTING
  - GREETING BEHAVIOR

This is ALWAYS generated — whether or not the user provides custom instructions.
If the user provides a user_instruction, it is appended into the relevant sections
and followed STRICTLY (not paraphrased or softened).

The skill .md file IS the system prompt injected into the static OS prompt
via the {persona_task} placeholder at runtime.
"""

import os
import re
from typing import Optional
from pydantic import BaseModel, Field

from ..engine.llm_gateway import StructuredChatClient
from ..utils.prompt_loader import PromptLoader

SKILLS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../skills/definitions'))
os.makedirs(SKILLS_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# LLM Response Model
# ─────────────────────────────────────────────────────────────────────────────

class SkillPromptResponse(BaseModel):
    """Structured output from the Skill Prompt Architect LLM call."""
    common_name: str = Field(description="The exact common_name of the agent — must match input.")
    system_prompt: str = Field(
        description=(
            "The full structured system prompt for this agent. "
            "Must include all 6 sections: PERSONA, TEAM DIRECTORY, COMMAND HIERARCHY, "
            "RESPONSIBILITIES, STRICT RULES & ROUTING, GREETING BEHAVIOR."
        )
    )
    agent_type: str = Field(
        description=(
            "The category of tools this agent needs based on its role. "
            "Choose exactly one of: 'chat' (human interaction only), 'interviewer' (chat + doc parsing), "
            "'writer' (file read/write), 'architect' (file + shell), 'researcher' (file + doc parsing + web search), "
            "'analyst' (file + shell execution)."
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Skill Generator
# ─────────────────────────────────────────────────────────────────────────────

class SkillGenerator:
    """
    Generates the per-agent system prompt (skill) during the unfreeze phase.

    Always generates — even if no user_instruction is provided.
    If user_instruction is provided, it is injected into the prompt architect
    and followed strictly in the relevant sections.

    Output is saved as a .md file in core/skills/definitions/{session_id}/
    and loaded at runtime as the agent's persona_task (injected into the OS prompt).
    """

    def __init__(self, llm_client: StructuredChatClient):
        self.llm_client = llm_client

    # ── File path helpers ──────────────────────────────────────────────────

    def _get_skill_file_path(self, agent_name: str, session_id: str = "default") -> str:
        session_dir = os.path.join(SKILLS_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)
        safe_name = agent_name.replace(" ", "_").replace("/", "").replace("\\", "")
        return os.path.join(session_dir, f"{safe_name}.md")

    def clear_session_skills(self, session_id: str = "default") -> None:
        """Delete all skill files for a session to force regeneration."""
        import shutil
        session_dir = os.path.join(SKILLS_DIR, session_id)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)

    # ── File I/O ───────────────────────────────────────────────────────────

    def load_system_prompt_from_file(self, agent_name: str, session_id: str = "default") -> Optional[str]:
        """
        Load the system prompt from the saved .md skill file.
        Returns the raw content (which IS the system prompt) or None if not found.
        """
        filepath = self._get_skill_file_path(agent_name, session_id)
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        return content if content else None

    def save_system_prompt_to_file(self, agent_name: str, system_prompt: str, session_id: str = "default") -> None:
        """Save the generated system prompt as a .md skill file."""
        filepath = self._get_skill_file_path(agent_name, session_id)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(system_prompt)

    # ── Tree helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_team_directory(root) -> str:
        """
        Walk the agent tree from root and produce a visual hierarchy string.
        Example:
            root_neuron (Task Coordinator)
            ├── neuron_1 (Backend Developer)
            └── neuron_2 (Code Reviewer)
        """
        lines = []

        def _walk(node, prefix: str, is_last: bool):
            connector = "└── " if is_last else "├── "
            role = f" ({node.dynamic_name})" if node.dynamic_name else ""
            lines.append(f"{prefix}{connector}{node.common_name}{role}")
            child_prefix = prefix + ("    " if is_last else "│   ")
            for i, child in enumerate(node.children):
                _walk(child, child_prefix, i == len(node.children) - 1)

        role = f" ({root.dynamic_name})" if root.dynamic_name else ""
        lines.append(f"{root.common_name}{role}  ← ROOT")
        for i, child in enumerate(root.children):
            _walk(child, "", i == len(root.children) - 1)

        return "\n".join(lines)

    # ── Core generation ────────────────────────────────────────────────────

    async def generate_system_prompt(
        self,
        agent_node,
        root_node,
        original_task: str,
        subtask_provided: str,
        session_id: str = "default",
        user_instruction: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Generate the full system prompt for an agent.

        Always generates fresh via LLM — unless a skill file already exists
        for this agent+session (manual developer override).

        Args:
            agent_node:       The AgentNode being assigned a skill.
            root_node:        The root of the agent tree (for team directory).
            original_task:    The master objective of the whole swarm.
            subtask_provided: This agent's specific assigned responsibility.
            session_id:       Session identifier for file scoping.
            user_instruction: Optional developer override — followed strictly.

        Returns:
            A tuple of (system_prompt, agent_type).
        """
        # 1. Check for existing manual override file first
        existing = self.load_system_prompt_from_file(agent_node.common_name, session_id)
        if existing:
            # If loaded from file, we don't have an auto-generated agent_type. Default to "writer".
            return existing, "writer"

        # 2. Build team directory from tree
        team_directory = self._build_team_directory(root_node)

        # 3. Build boss info
        boss_info = (
            f"{agent_node.parent.common_name} ({agent_node.parent.dynamic_name})"
            if agent_node.parent
            else "human (the user — you report directly to the human)"
        )

        # 4. Build subordinates info
        if agent_node.children:
            sub_lines = [
                f"  - {child.common_name} ({child.dynamic_name or 'role TBD'})"
                for child in agent_node.children
            ]
            subordinates_info = "\n".join(sub_lines)
        else:
            subordinates_info = "None — you are a leaf agent. Execute tasks directly using your tools."

        # 5. Build user instruction block
        # The FORMATION_BRIEF (original_task) is always injected as the primary context.
        # If the developer also provided a node-specific user_instruction, append it.
        formation_brief = original_task.strip() if original_task else ""
        node_instruction = user_instruction.strip() if user_instruction and user_instruction.strip() else ""

        if formation_brief and node_instruction:
            user_instruction_block = (
                f"FORMATION BRIEF (overall system intent):\n{formation_brief}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\nNODE-SPECIFIC INSTRUCTION\n━━━━━━━━━━━━━━━━━━━━\n{node_instruction}"
            )
        elif formation_brief:
            user_instruction_block = f"FORMATION BRIEF (overall system intent):\n{formation_brief}"
        elif node_instruction:
            user_instruction_block = (
                f"━━━━━━━━━━━━━━━━━━━━\nSTRICT USER INSTRUCTIONS\n━━━━━━━━━━━━━━━━━━━━\n{node_instruction}"
            )
        else:
            user_instruction_block = "(No formation brief provided — infer responsibilities from agent name and team directory.)"

        # 6. Load the Skill Prompt Architect template
        system_prompt_template = PromptLoader.get_prompt(
            "system/prompt_assignment.md",
            common_name=agent_node.common_name,
            team_directory=team_directory,
            boss_info=boss_info,
            subordinates_info=subordinates_info,
            user_instruction_block=user_instruction_block,
        )

        # 7. LLM call — generate the full system prompt
        user_content = (
            f"Generate the complete skill system prompt for the agent with common_name='{agent_node.common_name}', "
            f"role='{agent_node.dynamic_name or agent_node.common_name}'.\n"
            f"Their specific responsibility in this swarm: {subtask_provided}\n\n"
            f"MANDATORY: Extract and expand on the exact duties for '{agent_node.common_name}' from the FORMATION BRIEF. "
            f"Write explicit NUMBERED SEQUENTIAL STEPS for every subordinate delegation. "
            f"Include DONE conditions for each step. Include NEVER-SKIP rules. "
            f"Do NOT use vague IF/THEN routing — use numbered sequential steps only."
        )

        response: SkillPromptResponse = await self.llm_client.get_response(
            user_prompt=user_content,
            system_prompt=system_prompt_template,
            response_model=SkillPromptResponse,
        )

        # 8. Save to .md file
        self.save_system_prompt_to_file(agent_node.common_name, response.system_prompt, session_id)

        return response.system_prompt, response.agent_type
