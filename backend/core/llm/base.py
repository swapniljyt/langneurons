"""
core/llm/base.py
━━━━━━━━━━━━━━━━
LAYER  : LLM
ROLE   : The abstract contract every LLM provider must implement.

This is the heart of the plugin system. Any LLM — OpenAI, Anthropic, Moonshot,
Groq, Ollama, or a completely custom model — becomes a first-class LangNeurons
citizen by subclassing BaseLLMProvider and implementing two methods.

SOLID PRINCIPLE ENFORCED:
  Open/Closed  — Framework is open for extension, closed for modification.
                 Adding a new LLM never requires editing framework source files.
  Dependency Inversion — LLMConnector depends on this abstraction, NOT on any
                         concrete chat model class.

HOW TO IMPLEMENT YOUR OWN PROVIDER:
  from langneurons.core.llm import BaseLLMProvider, register_provider

  class GroqProvider(BaseLLMProvider):
      name = "groq"

      def create_router_llm(self):
          from langchain_groq import ChatGroq
          return ChatGroq(model="llama-3.1-8b-instant")

      def create_execution_llm(self, use_thinking=False):
          from langchain_groq import ChatGroq
          return ChatGroq(model="llama-3.3-70b-versatile")

  register_provider(GroqProvider)

  # Then set LLM_PROVIDER=groq in your .env file.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.language_models.chat_models import BaseChatModel


class BaseLLMProvider(ABC):
    """
    Abstract base class for all LangNeurons LLM providers.

    Subclass this to integrate any LangChain-compatible LLM into LangNeurons.
    Each provider is responsible for creating two tiers of LLM:

      - ROUTER tier  : fast, cheap, used for structured agent delegation decisions.
                       Must be compatible with .with_structured_output().
                       NEVER uses thinking mode.

      - EXECUTION tier: powerful, used for tool-calling and multi-step reasoning.
                        Optionally supports a native thinking/reasoning mode.

    Class Attributes:
        name (str): Unique string identifier registered in LLMProviderRegistry.
                    Must match the value set in the LLM_PROVIDER env var.
                    Example: "moonshot", "openai", "anthropic", "google"
    """

    # Subclasses MUST set this as a class attribute, not an instance attribute.
    name: str = ""

    @abstractmethod
    def create_router_llm(self) -> BaseChatModel:
        """
        Create the ROUTER LLM instance.

        This model handles structured delegation decisions.
        It must be fast, cheap, and compatible with .with_structured_output().
        It MUST NOT use thinking mode.

        Returns:
            A configured LangChain BaseChatModel instance.
        """
        ...

    @abstractmethod
    def create_execution_llm(self, use_thinking: bool = False) -> BaseChatModel:
        """
        Create the EXECUTION LLM instance.

        This model handles tool-calling, code generation, and complex reasoning.

        Args:
            use_thinking: If True AND the provider supports it (supports_thinking()
                          returns True), enable the provider's native reasoning mode.
                          Providers that do not support thinking simply ignore this flag.

        Returns:
            A configured LangChain BaseChatModel instance.
        """
        ...

    def create_vision_llm(self) -> BaseChatModel:
        """
        Create the VISION LLM instance.

        This model handles multimodal tasks (such as visual layout audits) by accepting both text prompts and images.
        Subclasses should override this if they support vision natively.
        By default, raises NotImplementedError if not overridden by the provider.
        """
        raise NotImplementedError(f"Vision model capability not implemented for the '{self.name}' provider.")

    def supports_thinking(self) -> bool:
        """
        Override to return True if this provider has a native thinking/reasoning mode.

        When True, the LLMConnector will pass use_thinking=True to create_execution_llm()
        for agents classified as thinking-capable (architect, analyst, runner, writer).

        Default: False (thinking not supported).
        """
        return False

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Enforce that every subclass declares a non-empty `name` attribute."""
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "name", ""):
            raise TypeError(
                f"{cls.__name__} must define a class-level 'name' attribute. "
                f"Example: name = 'my_provider'"
            )
