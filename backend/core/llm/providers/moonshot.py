import os
from langchain_core.language_models.chat_models import BaseChatModel
from ..base import BaseLLMProvider

class MoonshotProvider(BaseLLMProvider):
    name = "moonshot"

    def supports_thinking(self) -> bool:
        return True

    def create_router_llm(self) -> BaseChatModel:
        try:
            from langchain_moonshot import ChatMoonshot
        except ImportError:
            raise ImportError("Please install langchain-moonshot to use Moonshot models.")

        api_key = os.getenv("MOONSHOT_API_KEY")
        if not api_key:
            raise ValueError("MOONSHOT_API_KEY environment variable is missing.")

        model_name = os.getenv("MODEL_ROUTER_MOONSHOT", "moonshot-v1-8k")

        temp = 0.6 if model_name == "kimi-k2.5" else 0.1

        return ChatMoonshot(
            model=model_name,
            api_key=api_key,
            temperature=temp,
            thinking=False,
        )

    def create_execution_llm(self, use_thinking: bool = False) -> BaseChatModel:
        try:
            from langchain_moonshot import ChatMoonshot
        except ImportError:
            raise ImportError("Please install langchain-moonshot to use Moonshot models.")

        api_key = os.getenv("MOONSHOT_API_KEY")
        if not api_key:
            raise ValueError("MOONSHOT_API_KEY environment variable is missing.")

        model_name = os.getenv("MODEL_EXEC_MOONSHOT", "kimi-k2.5")

        if use_thinking:
            return ChatMoonshot(
                model=model_name,
                api_key=api_key,
                temperature=1.0,
                thinking=True,
            )
        else:
            return ChatMoonshot(
                model=model_name,
                api_key=api_key,
                temperature=0.6,
                thinking=False,
            )

    def create_vision_llm(self) -> BaseChatModel:
        try:
            from langchain_moonshot import ChatMoonshot
        except ImportError:
            raise ImportError("Please install langchain-moonshot to use Kimi Moonshot vision models.")

        api_key = os.getenv("MOONSHOT_API_KEY")
        if not api_key:
            raise ValueError("MOONSHOT_API_KEY environment variable is missing.")

        model_name = os.getenv("MODEL_VISION_MOONSHOT") or os.getenv("VISION_MODEL") or "moonshot-v1-8k-vision-preview"
        return ChatMoonshot(
            model=model_name,
            api_key=api_key,
            temperature=0.2,
            thinking=False,
        )
