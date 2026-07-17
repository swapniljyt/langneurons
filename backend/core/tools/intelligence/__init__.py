"""
core/tools/intelligence
────────────────────────
Shared Engineering Intelligence (SEI) population tools.
Reserved for the root_neuron / project coordinator only.

Public exports:
  create_sei_tools  — factory: returns all 5 SEI tools bound to a session_id
"""

from .sei_tools import create_sei_tools

__all__ = ["create_sei_tools"]
