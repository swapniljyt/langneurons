import os
from langchain_core.language_models.chat_models import BaseChatModel
from ..base import BaseLLMProvider

class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"

    def supports_thinking(self) -> bool:
        return False # Anthropic doesn't have an explicit 'thinking' boolean parameter in ChatAnthropic yet like Kimi.

    def create_router_llm(self) -> BaseChatModel:
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError("Please install langchain-anthropic to use Claude models.")

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is missing.")

        model_name = os.getenv("MODEL_ROUTER_ANTHROPIC", "claude-3-5-haiku-20241022")

        return ChatAnthropic(
            model_name=model_name,
            anthropic_api_key=api_key,
            temperature=0.1,
        )

    def create_execution_llm(self, use_thinking: bool = False) -> BaseChatModel:
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError("Please install langchain-anthropic to use Claude models.")

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is missing.")

        model_name = os.getenv("MODEL_EXEC_ANTHROPIC", "claude-3-5-sonnet-20241022")

        return ChatAnthropic(
            model_name=model_name,
            anthropic_api_key=api_key,
            temperature=0.1,
        )
