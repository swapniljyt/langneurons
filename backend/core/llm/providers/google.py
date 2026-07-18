import os
from langchain_core.language_models.chat_models import BaseChatModel
from ..base import BaseLLMProvider

class GoogleProvider(BaseLLMProvider):
    name = "gemini"

    def supports_thinking(self) -> bool:
        return False # Gemini reasoning models exist, but via separate model strings rather than a boolean toggle right now.

    def create_router_llm(self) -> BaseChatModel:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError("Please install langchain-google-genai to use Gemini models.")

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing.")

        model_name = os.getenv("MODEL_ROUTER_GEMINI") or os.getenv("MODEL_GEMINI_ROUTER") or "gemini-2.5-flash"

        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.1,
        )

    def create_execution_llm(self, use_thinking: bool = False) -> BaseChatModel:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError("Please install langchain-google-genai to use Gemini models.")

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing.")

        model_name = os.getenv("MODEL_EXEC_GEMINI") or os.getenv("MODEL_GEMINI") or "gemini-2.5-pro"

        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.1,
        )

    def create_vision_llm(self) -> BaseChatModel:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError("Please install langchain-google-genai to use Gemini models.")

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing.")

        model_name = os.getenv("MODEL_GEMINI_ROUTER") or "gemini-2.5-flash"

        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.2,
        )
