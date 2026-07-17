"""
core/llm/registry.py
━━━━━━━━━━━━━━━━━━━━
LAYER  : LLM
ROLE   : Central registry — stores and resolves LLM provider classes by name.

The registry is the glue between user code and the framework. It decouples
LLMConnector from any concrete provider implementation.

PATTERN: Service Locator / Registry
  - Providers register themselves by class (not instance).
  - The registry instantiates on demand — one fresh instance per call.
  - Built-in providers auto-register on import via _register_builtin_providers().

CALLED BY:
  • core/llm/connector.py → LLMConnector.get_llm()

EXAMPLE (user-side):
  from langneurons.core.llm import BaseLLMProvider, register_provider

  class MyProvider(BaseLLMProvider):
      name = "my_llm"
      ...

  register_provider(MyProvider)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseLLMProvider


class LLMProviderRegistry:
    """
    Thread-safe, class-level registry for LLM provider classes.

    Storage is at the class level (not instance level), so all code
    shares a single registry without needing a singleton object.
    """

    _providers: dict[str, type["BaseLLMProvider"]] = {}

    # ── Registration ──────────────────────────────────────────────────────────

    @classmethod
    def register(cls, provider_class: type["BaseLLMProvider"]) -> None:
        """
        Register a provider class by its declared name.

        Overwrites any existing registration for the same name, allowing
        users to swap built-in providers with custom implementations.

        Args:
            provider_class: A concrete subclass of BaseLLMProvider.
                            Must have a non-empty `name` class attribute.

        Raises:
            TypeError: If provider_class is not a BaseLLMProvider subclass.
        """
        from .base import BaseLLMProvider

        if not issubclass(provider_class, BaseLLMProvider):
            raise TypeError(
                f"Cannot register {provider_class.__name__}: "
                f"must be a subclass of BaseLLMProvider."
            )
        cls._providers[provider_class.name.lower()] = provider_class

    # ── Resolution ────────────────────────────────────────────────────────────

    @classmethod
    def get(cls, name: str) -> "BaseLLMProvider":
        """
        Retrieve and instantiate a provider by name.

        Args:
            name: The provider identifier (e.g. "moonshot", "openai").
                  Case-insensitive.

        Returns:
            A fresh instance of the registered provider class.

        Raises:
            ValueError: If no provider is registered under this name.
        """
        key = name.lower()
        if key not in cls._providers:
            available = sorted(cls._providers.keys())
            raise ValueError(
                f"Unknown LLM provider: '{name}'.\n"
                f"  Available built-in providers : {available}\n"
                f"  To add a custom provider     : register_provider(MyProvider)\n"
                f"  Docs                         : see core/llm/base.py"
            )
        return cls._providers[key]()

    # ── Introspection ─────────────────────────────────────────────────────────

    @classmethod
    def list_providers(cls) -> list[str]:
        """Return all registered provider names, sorted alphabetically."""
        return sorted(cls._providers.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Return True if a provider with this name is registered."""
        return name.lower() in cls._providers


def register_provider(provider_class: type["BaseLLMProvider"]) -> None:
    """
    Public convenience function for registering a custom provider.

    This is the ONLY function users need to call to add a new LLM.

    Args:
        provider_class: A concrete subclass of BaseLLMProvider.

    Example:
        from langneurons.core.llm import register_provider, BaseLLMProvider

        class GroqProvider(BaseLLMProvider):
            name = "groq"
            def create_router_llm(self): ...
            def create_execution_llm(self, use_thinking=False): ...

        register_provider(GroqProvider)
    """
    LLMProviderRegistry.register(provider_class)
