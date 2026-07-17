"""
LangNeurons — Production-grade hierarchical multi-agent swarm framework.

This is the public API. Users should import from here rather than 
digging into the internal directory structure.
"""

# Swarm Execution
from .swarm import run_swarm

# Agent Definition
from .agents.agent_node import AgentNode

# LLM Extensibility
from .llm.base import BaseLLMProvider
from .llm.registry import register_provider

# Tool & Agent Extensibility
from .tools.registry import register_tool, register_agent_type

__all__ = [
    # Swarm
    "run_swarm",
    
    # Agents
    "AgentNode",
    
    # Custom LLMs
    "BaseLLMProvider",
    "register_provider",
    
    # Custom Tools & Roles
    "register_tool",
    "register_agent_type",
]
