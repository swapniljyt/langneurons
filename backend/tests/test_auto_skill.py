import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.modules.skill_generator import SkillGenerator
from core.engine.llm_gateway import StructuredChatClient

async def main():
    print("🚀 Starting direct SkillGeneration Test...")
    llm = StructuredChatClient()
    generator = SkillGenerator(llm)

    skill = await generator.generate_skill(
        role="Resume Parser",
        original_task="Parse resumes and identify AI experience",
        subtask_provided="Extract any mention of LangChain, OpenAI, or LLMs from the PDF and output to agent_metadata."
    )

    print(f"\n✅ GENERATED SKILL: {skill.name}")
    print(f"INSTRUCTIONS: {skill.instructions}")
    print(f"START: {skill.start_trigger}")
    print(f"END: {skill.end_condition}")
    print(f"KEYS: {skill.output_metadata_keys}")

if __name__ == "__main__":
    asyncio.run(main())
