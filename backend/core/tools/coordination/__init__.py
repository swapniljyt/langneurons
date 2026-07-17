"""
core/tools/coordination
────────────────────────
Team-coordination tools: API contract publishing and reading.

Public exports:
  publish_contract  — publish API routes/schemas so other agents can consume them
  read_contracts    — read what the backend team has published
"""

from .contracts import publish_contract, read_contracts

__all__ = ["publish_contract", "read_contracts"]
