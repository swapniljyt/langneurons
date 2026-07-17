"""
core/llm/connector.py
━━━━━━━━━━━━━━━━━━━━━
LAYER  : LLM
ROLE   : Thin facade for retrieving LLM instances from the registry.

This module used to contain massive if/elif chains and direct provider
instantiations. It has been refactored to use the Strategy + Registry
patterns.

Now, it simply reads the LLM_PROVIDER env var, asks the registry for
that provider, and calls its standard methods.

THINKING MODE — Selective by agent_type:
  Enabled for : architect, analyst, runner, writer
  Disabled for: chat, interviewer, assembler, researcher
  Rule        : Router LLM NEVER uses thinking (incompatible with structured output).
"""

import os
from typing import Literal
from pathlib import Path
from dotenv import load_dotenv

from langchain_core.language_models.chat_models import BaseChatModel

from .registry import LLMProviderRegistry

# Ensure built-in providers are registered by importing the providers package
import core.llm.providers

# Load environment variables
BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

# ── Thinking-capable agent types ──────────────────────────────────────────────
# These agent types receive thinking=True on the execution LLM, if the provider
# supports it (e.g. Moonshot kimi-k2.5).
THINKING_AGENT_TYPES: frozenset[str] = frozenset({
    "architect",  # multi-file design, system planning
    "analyst",    # data pipelines, shell + analysis
    "runner",     # debugging, error fixing, build execution
    "writer",     # code writing and generation
})


class LLMConnector:
    """
    Facade for retrieving LLM instances.

    Delegates to the registered BaseLLMProvider.
    """

    @classmethod
    def get_llm(
        cls,
        purpose: Literal["router", "execution", "vision"] = "execution",
        temperature: float = 0.1,  # Kept for backward compatibility but mostly handled by providers now
        agent_type: str = "",
    ) -> BaseChatModel:
        """
        Get a ChatModel instance configured for the specified purpose.

        Args:
            purpose:    "router" (fast, structured output),
                        "execution" (smart, tool-calling, optional thinking), or
                        "vision" (multimodal vision capabilities)
            temperature: Legacy compat param, now mostly handled by providers internally.
            agent_type:  The agent's capability type (e.g. "architect", "writer").

        Returns:
            A LangChain BaseChatModel instance.
        """
        provider_name = os.getenv("LLM_PROVIDER", "moonshot").lower()
        provider = LLMProviderRegistry.get(provider_name)

        if purpose == "router":
            return provider.create_router_llm()
        elif purpose == "vision":
            return provider.create_vision_llm()
        else:
            # Only enable thinking if the agent type warrants it AND the provider supports it
            use_thinking = (
                agent_type in THINKING_AGENT_TYPES
                and provider.supports_thinking()
            )
            return provider.create_execution_llm(use_thinking=use_thinking)


def is_thinking_agent(agent_type: str) -> bool:
    """
    Returns True if the given agent_type should use thinking mode.
    Respects the global _GLOBAL_THINKING_ENABLED flag from agent_factory —
    if that flag is False, always returns False regardless of agent_type.
    """
    try:
        from core.engine.agent_factory import _GLOBAL_THINKING_ENABLED
        if not _GLOBAL_THINKING_ENABLED:
            return False
    except ImportError:
        pass
    return agent_type in THINKING_AGENT_TYPES
