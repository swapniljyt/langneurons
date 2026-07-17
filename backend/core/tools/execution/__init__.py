"""
core/tools/execution
─────────────────────
Shell-execution tools for Runner agents.

Public exports:
  execute_command      — run a bash command in the sandbox
  create_runner_tools  — factory: returns session-scoped suggest_fix tool
"""

from .runner import execute_command, create_runner_tools

__all__ = ["execute_command", "create_runner_tools"]
