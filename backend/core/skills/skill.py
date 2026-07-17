"""
core/skills/skill.py
━━━━━━━━━━━━━━━━━━━━
The Skill class — a pluggable unit of structured responsibility for any agent.

A Skill defines:
  1. WHAT the agent should do (instructions)
  2. WHEN it should start (start_trigger)
  3. WHEN it should stop (end_condition)
  4. WHAT metadata keys to update when done (output_metadata_keys)
  5. WHAT tools it can use to accomplish the task (tools — optional)

Usage:
    from core.skills import Skill

    # Pure knowledge skill (no tools)
    greeting_skill = Skill(
        name="candidate_greeting",
        instructions="Greet the candidate warmly, ask their name, set a friendly tone.",
        start_trigger="Router delegates to you for introduction",
        end_condition="Candidate has been greeted and responded",
        output_metadata_keys=["greeted", "candidate_name"],
    )

    # Skill with tools
    resume_skill = Skill(
        name="resume_parsing",
        instructions="Extract name, email, phone, skills, experience from resume text.",
        start_trigger="HR Supervisor delegates resume parsing task",
        end_condition="All resume fields extracted and stored in metadata",
        output_metadata_keys=["resume_parsed", "candidate_info"],
        tools=[read_pdf_tool, extract_text_tool],
    )

    # Attach to agent
    agent_node.add_skill(greeting_skill)
"""

from __future__ import annotations
from typing import Callable, Optional
from pydantic import BaseModel, Field


class Skill(BaseModel):
    """
    A pluggable unit of structured responsibility for a LangNeurons agent.

    Skills are the bridge between the system prompt (WHO the agent is)
    and the tools (WHAT the agent can do). A skill defines HOW the agent
    should accomplish its responsibility.

    Conceptual model:
        System Prompt  →  WHO I am, my role, my rules
        Skill          →  HOW I do my job (strategy + start/end rules)
        Tools          →  WHAT actions I can take (optional)
    """

    name: str = Field(
        description="Unique identifier for this skill, e.g. 'resume_parsing', 'candidate_greeting'"
    )

    instructions: str = Field(
        description=(
            "Detailed instructions on HOW to perform this skill. "
            "This gets injected into the agent's prompt so the LLM knows "
            "the exact strategy to follow."
        )
    )

    start_trigger: str = Field(
        description=(
            "WHEN this skill activates. e.g. 'Router delegates to me for introduction', "
            "'HR Supervisor assigns resume parsing task'. "
            "The agent checks this to know if it should act."
        )
    )

    end_condition: str = Field(
        description=(
            "WHAT marks this skill as fully done. e.g. 'Candidate has been greeted', "
            "'All resume fields extracted'. The agent checks this to know when to "
            "report 'complete' and stop."
        )
    )

    output_metadata_keys: list[str] = Field(
        default_factory=list,
        description=(
            "Metadata keys this skill MUST update when done. "
            "e.g. ['resume_parsed', 'candidate_info']. "
            "The execution engine checks these keys to confirm completion."
        )
    )

    # ── Optional: Tools ──────────────────────────────────────────────────────
    # Note: tools are NOT serializable by Pydantic, so we store them separately
    # and exclude from model serialization. The StructuredInvoker handles binding.

    class Config:
        arbitrary_types_allowed = True

    def format_for_prompt(self) -> str:
        """
        Format this skill as a structured block for injection into the agent's prompt.
        This is called by StructuredInvoker when building the agent's context.
        """
        lines = [
            f"━━━━━━━━━━━━━━━━━━━━",
            f"SKILL: {self.name}",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"",
            f"⚠️ BEFORE ACTING: Check TEAM KNOWLEDGE and ORGANIZATIONAL TIMELINE above.",
            f"   If another agent already collected the data you need, USE IT. Do NOT re-ask the user.",
            f"",
            f"INSTRUCTIONS:",
            f"{self.instructions}",
            f"",
            f"START TRIGGER: {self.start_trigger}",
            f"END CONDITION: {self.end_condition}",
        ]

        if self.output_metadata_keys:
            keys_str = ", ".join(self.output_metadata_keys)
            lines.append(f"")
            lines.append(f"REQUIRED METADATA UPDATES (you MUST set these in agent_metadata when done):")
            lines.append(f"  Keys: [{keys_str}]")
            lines.append(f"")
            lines.append(f"ON COMPLETION — you MUST also produce:")
            lines.append(f"  responsibility_report: {{completed_tasks: [...], incomplete_tasks: [...], blocked_by: [...]}}")
            lines.append(f"  responsibility_metadata: {{...all structured data you collected/generated...}}")

        return "\n".join(lines)


class SkillRegistry:
    """
    Central registry of all available skills for quick lookup.
    Users can register skills globally and then attach them by name.

    Usage:
        registry = SkillRegistry()
        registry.register(greeting_skill)
        registry.register(resume_skill)

        # Later, attach to agent by name
        agent_node.add_skill(registry.get("candidate_greeting"))
    """

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._tools: dict[str, list[Callable]] = {}  # skill_name → tools list

    def register(self, skill: Skill, tools: list[Callable] = None) -> None:
        """Register a skill (and optionally its tools) in the registry."""
        self._skills[skill.name] = skill
        if tools:
            self._tools[skill.name] = tools

    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(name)

    def get_tools(self, name: str) -> list[Callable]:
        """Get the tools attached to a skill."""
        return self._tools.get(name, [])

    def list_skills(self) -> list[str]:
        """List all registered skill names."""
        return list(self._skills.keys())
