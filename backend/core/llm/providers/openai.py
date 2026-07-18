import os
from langchain_core.language_models.chat_models import BaseChatModel
from ..base import BaseLLMProvider

class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    def supports_thinking(self) -> bool:
        return False # O1 models handle reasoning internally without a specific toggle in ChatOpenAI

    def create_router_llm(self) -> BaseChatModel:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError("Please install langchain-openai to use OpenAI models.")

        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is missing.")

        model_name = os.getenv("MODEL_ROUTER_OPENAI") or os.getenv("MODEL_OPENAI_ROUTER") or "gpt-4o-mini"

        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            temperature=0.1,
        )

    def create_execution_llm(self, use_thinking: bool = False) -> BaseChatModel:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError("Please install langchain-openai to use OpenAI models.")

        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is missing.")

        model_name = os.getenv("MODEL_EXEC_OPENAI") or os.getenv("MODEL_OPENAI") or "gpt-4o"

        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            temperature=0.1,
        )

    def create_vision_llm(self) -> BaseChatModel:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError("Please install langchain-openai to use OpenAI models.")

        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is missing.")

        model_name = os.getenv("MODEL_ROUTER_OPENAI") or "gpt-4o-mini"

        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            temperature=0.2,
        )
