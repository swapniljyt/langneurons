# core/skills — LangNeurons Skill System
#
# Skills are pluggable units of structured responsibility.
# They define HOW an agent does its job: instructions, start/end conditions,
# required metadata updates, and optional tools.
#
# Usage:
#     from core.skills import Skill, SkillRegistry

from .skill import Skill, SkillRegistry
from .skill_tool import create_load_skill_tool

__all__ = ["Skill", "SkillRegistry", "create_load_skill_tool"]
