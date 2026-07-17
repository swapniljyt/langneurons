import os
import asyncio
from typing import Type, TypeVar, List, Union
from dotenv import load_dotenv
from pydantic import BaseModel
from pathlib import Path

# Resiliency
from tenacity import retry, wait_exponential, stop_after_attempt

# LangChain Imports
from langchain_core.messages import SystemMessage, HumanMessage
from ..llm.connector import LLMConnector

# Load environment variables
BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

T = TypeVar("T", bound=BaseModel)

class StructuredChatClient:
    """Unified LLM Client using LLMConnector"""
    def __init__(self, model: str = None):
        # We use the smart execution model by default for module logic
        self.llm = LLMConnector.get_llm(purpose="execution")

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=20),
        stop=stop_after_attempt(5),
        reraise=True
    )
    async def get_response(
        self,
        user_prompt: str,
        system_prompt: str,
        response_model: Type[T],
        executor=None,
        loop=None
    ) -> T:
        """
        Get structured response from the API using LangChain's with_structured_output.
        """
        # Create a structured LLM runnable
        provider = os.getenv("LLM_PROVIDER", "moonshot").lower()
        if provider == "openrouter":
            model_name = getattr(self.llm, "model", "") or ""
            if ":free" in model_name:
                # Some OpenRouter free tier models require tool_choice="auto" 
                # and reject forced tool names, which with_structured_output uses by default.
                from langchain_core.output_parsers.openai_tools import PydanticToolsParser
                structured_llm = self.llm.bind_tools(
                    [response_model], tool_choice="auto"
                ) | PydanticToolsParser(tools=[response_model], first_tool_only=True)
            else:
                structured_llm = self.llm.with_structured_output(response_model)
        elif provider in ["openai", "moonshot"]:
            structured_llm = self.llm.with_structured_output(response_model, method="function_calling")
        else:
            structured_llm = self.llm.with_structured_output(response_model)
        
        # Create messages directly
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        # Use async invoke
        response = await structured_llm.ainvoke(messages)
        if response is None:
            raise ValueError("LLM failed to return a structured response (None).")
        return response

class StructuredGeminiClient:
    """Google Gemini LLM Client using LangChain"""
    def __init__(self, model: str = None, return_list: bool = False):
        self.api_key = os.getenv("GEMINI_API")
        if not self.api_key:
            raise ValueError("❌ GEMINI_API key not found in .env")

        self.model_name = model or os.getenv("MODEL_GEMINI", "gemini-2.5-flash")
        self.return_list = return_list
        
        # Initialize ChatGoogleGenerativeAI
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=self.api_key,
            temperature=0.1,
            convert_system_message_to_human=True
        )

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=20),
        stop=stop_after_attempt(5),
        reraise=True
    )
    async def get_response(
        self,
        user_prompt: str,
        system_prompt: str,
        response_model: Type[T]
    ) -> Union[T, List[T]]:
        
        target_schema = response_model
        
        # For Gemini, we use with_structured_output
        structured_llm = self.llm.with_structured_output(target_schema)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        result = await structured_llm.ainvoke(messages)
        if result is None:
            raise ValueError("Gemini failed to return a structured response (None).")
        return result

