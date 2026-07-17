"""
core/llm/providers/openrouter.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OpenRouter LLM provider for LangNeurons.

OpenRouter is a unified gateway that routes to 100+ models from Anthropic,
OpenAI, Google, Meta, DeepSeek, Mistral, and more — through one API key.

SETUP
─────
1. Create an account at https://openrouter.ai and grab an API key.
2. Add to your .env:

       LLM_PROVIDER=openrouter
       OPENROUTER_API_KEY=sk-or-...

       # Router model (fast, cheap — for delegation decisions)
       MODEL_ROUTER_OPENROUTER=google/gemini-flash-1.5

       # Execution model (powerful — for code writing, tool use)
       MODEL_EXEC_OPENROUTER=anthropic/claude-sonnet-4-5

       # Optional: enable thinking on supported models (claude-sonnet-4-5,
       # deepseek/deepseek-r1, etc.)
       OPENROUTER_THINKING_EFFORT=high   # xhigh / high / medium / low / minimal / none

3. Any model slug from https://openrouter.ai/models works.

STRUCTURED OUTPUT
─────────────────
OpenRouter uses the OpenAI-compatible tool-calling format, so
.with_structured_output() works out of the box with function_calling.
"""

import os
from langchain_core.language_models.chat_models import BaseChatModel
from ..base import BaseLLMProvider


class OpenRouterProvider(BaseLLMProvider):
    name = "openrouter"

    # Models that natively support OpenRouter's `reasoning` parameter
    THINKING_MODELS = {
        "anthropic/claude-sonnet-4-5",
        "anthropic/claude-opus-4",
        "anthropic/claude-3-7-sonnet",
        "deepseek/deepseek-r1",
        "deepseek/deepseek-r1-distill-llama-70b",
        "openai/o1",
        "openai/o1-mini",
        "openai/o3",
        "openai/o3-mini",
        "google/gemini-2.5-pro-preview",
        "google/gemini-2.5-flash",
    }

    def supports_thinking(self) -> bool:
        exec_model = os.getenv("MODEL_EXEC_OPENROUTER", "anthropic/claude-sonnet-4-5")
        # Check if model slug starts with any thinking-capable prefix
        thinking_prefixes = ("anthropic/claude-3", "anthropic/claude-sonnet-4",
                             "anthropic/claude-opus-4", "deepseek/deepseek-r1",
                             "openai/o1", "openai/o3", "google/gemini-2.5")
        return (
            exec_model in self.THINKING_MODELS
            or any(exec_model.startswith(p) for p in thinking_prefixes)
        )

    def _get_api_key(self) -> str:
        key = os.getenv("OPENROUTER_API_KEY")
        if not key:
            raise ValueError(
                "OPENROUTER_API_KEY is not set. "
                "Get one at https://openrouter.ai/settings/keys "
                "and add it to your .env file."
            )
        return key

    def _build_extra_headers(self) -> dict:
        """
        Optional attribution headers for openrouter.ai dashboard.
        NOTE: langchain-openrouter currently does NOT forward these to Chat.send(),
        so they are built here for future compatibility but not injected into kwargs.
        """
        headers = {}
        app_url   = os.getenv("OPENROUTER_APP_URL", "")
        app_title = os.getenv("OPENROUTER_APP_TITLE", "")
        if app_url:
            headers["HTTP-Referer"] = app_url
        if app_title:
            headers["X-Title"] = app_title
        return headers

    # ── Router LLM ────────────────────────────────────────────────────────

    def create_router_llm(self) -> BaseChatModel:
        try:
            from langchain_openrouter import ChatOpenRouter
        except ImportError:
            raise ImportError(
                "langchain-openrouter is not installed.\n"
                "Run: pip install langchain-openrouter"
            )

        api_key    = self._get_api_key()
        model_name = os.getenv("MODEL_ROUTER_OPENROUTER", "google/gemini-flash-1.5")

        return ChatOpenRouter(
            model=model_name,
            openrouter_api_key=api_key,
            temperature=0.1,
        )

    # ── Execution LLM ─────────────────────────────────────────────────────

    def create_execution_llm(self, use_thinking: bool = False) -> BaseChatModel:
        try:
            from langchain_openrouter import ChatOpenRouter
        except ImportError:
            raise ImportError(
                "langchain-openrouter is not installed.\n"
                "Run: pip install langchain-openrouter"
            )

        api_key    = self._get_api_key()
        model_name = os.getenv("MODEL_EXEC_OPENROUTER", "anthropic/claude-sonnet-4-5")

        kwargs: dict = dict(
            model=model_name,
            openrouter_api_key=api_key,
            temperature=0.1,
        )

        # Enable reasoning for supported models when requested
        if use_thinking and self.supports_thinking():
            effort = os.getenv("OPENROUTER_THINKING_EFFORT", "high")
            kwargs["reasoning"] = {"effort": effort, "summary": "auto"}

        return ChatOpenRouter(**kwargs)

    def create_vision_llm(self) -> BaseChatModel:
        try:
            from langchain_openrouter import ChatOpenRouter
        except ImportError:
            raise ImportError(
                "langchain-openrouter is not installed.\n"
                "Run: pip install langchain-openrouter"
            )

        api_key    = self._get_api_key()
        # Default to google/gemini-2.5-flash which is widely used for multimodal vision tasks on OpenRouter
        model_name = os.getenv("MODEL_VISION_OPENROUTER") or os.getenv("VISION_MODEL") or "google/gemini-2.5-flash"

        return ChatOpenRouter(
            model=model_name,
            openrouter_api_key=api_key,
            temperature=0.2,
        )
