import os
import json
import asyncio
from redis import Redis
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict
from pydantic import BaseModel
from .llm_gateway import StructuredChatClient
from ..utils.prompt_loader import PromptLoader

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

class RedisClient:
    def __init__(self, db: int = 0, decode_responses: bool = False):
        """
        Initialize Redis client on class instantiation.
        Supports REDIS_URL or host/port/password environment variables.
        """
        try:
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                self.client = Redis.from_url(redis_url, db=db, decode_responses=decode_responses)
            else:
                host = os.getenv("REDIS_HOST", "localhost")
                port = int(os.getenv("REDIS_PORT", 6379))
                password = os.getenv("REDIS_PASSWORD")
                if password == "":
                    password = None
                self.client = Redis(
                    host=host,
                    port=port,
                    password=password,
                    db=db,
                    decode_responses=decode_responses,
                )
        except Exception as e:
            print("❌ Error initializing Redis client:", e)
            self.client = None

    def get_client(self) -> Redis:
        """Return the Redis client instance."""
        if self.client is None:
            # Try reconnecting or raise
            raise RuntimeError("Redis client is not initialized.")
        return self.client

# Context Checking Logic
class ContextMatchResult(BaseModel):
    is_context_match: bool

class Memory:
    """
    Memory & Context System.
    Handles context checking and retrieval.
    """
    def __init__(self, llm_client: StructuredChatClient):
        self.llm_client = llm_client

    def is_context_empty(self, context: List[dict]) -> bool:
        """Check if context is empty or contains only empty values."""
        return not context or all(not d or not list(d.values())[0] for d in context)

    async def check_context_match(self, context: List[dict], original_task: str) -> bool:
        """Advanced context matching with domain analysis."""
        if self.is_context_empty(context):
            return False
        
        # Extract and structure context
        conversations = []
        for item in context:
            if isinstance(item, dict):
                for key, value in item.items():
                    if value and str(value).strip():
                        conversations.append(value.strip())
        
        # Get the most recent conversation for primary analysis
        latest_conversation = conversations[-1] if conversations else ""
        all_conversations = " | ".join(conversations)
        
        system_prompt = PromptLoader.get_prompt("system/context_check.md")

        user_content = f"""PREVIOUS CONVERSATIONS: {all_conversations}

LATEST CONVERSATION: {latest_conversation}

CURRENT TASK: {original_task}

Question: Is the current task a logical follow-up or extension of the previous work?

Answer:"""

        try:
            # Call LLM for structured response
            completion = await self.llm_client.get_response(
                user_prompt=user_content,
                system_prompt=system_prompt,
                response_model=ContextMatchResult,
            )

            return completion.is_context_match
        except Exception as e:
            print(f"Error in advanced context matching: {str(e)}")
            return False
