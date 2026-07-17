"""
core/llm/providers/__init__.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Auto-registers all built-in LLM providers.
"""

from .moonshot import MoonshotProvider
from .anthropic import AnthropicProvider
from .google import GoogleProvider
from .openai import OpenAIProvider
from .openrouter import OpenRouterProvider
from .bedrock import BedrockProvider

from ..registry import register_provider

register_provider(MoonshotProvider)
register_provider(AnthropicProvider)
register_provider(GoogleProvider)
register_provider(OpenAIProvider)
register_provider(OpenRouterProvider)
register_provider(BedrockProvider)
