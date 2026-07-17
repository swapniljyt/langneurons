from typing import List
from langchain_core.tools import tool
from .skill import Skill

def create_load_skill_tool(skills: List[Skill]):
    """
    Creates a LangChain tool that allows a ReAct agent to dynamically
    load specialized skill prompts and instructions by name.
    """
    skill_map = {s.name: s for s in skills}
    
    # We dynamically generate the docstring so the LLM knows which skills are available
    available_skills_str = "\n".join(f"    - {name}" for name in skill_map.keys())
    
    if not available_skills_str:
        available_skills_str = "    (No skills available)"
        
    docstring = f"""Load a specialized skill prompt.

    Available skills:
{available_skills_str}

    Returns the skill's specific instructions, start triggers, and end conditions.
    """

    @tool
    def load_skill(skill_name: str) -> str:
        """Load a specialized skill prompt."""
        if skill_name not in skill_map:
            return f"Error: Skill '{skill_name}' not found. Available skills: {list(skill_map.keys())}"
        
        return skill_map[skill_name].format_for_prompt()
        
    # Override the docstring so LangChain passes it to the LLM
    load_skill.description = docstring
    
    return load_skill
