"""
core/tools/handoff
───────────────────
Human-in-the-loop handoff tools.
These pause swarm execution and collect real-time input from the user
at the terminal. Designed for conversational/interview-style agents.

Public exports:
  ask_human         — ask the user a single question; returns their answer
  ask_human_multi   — ask a list of questions; returns {question: answer} dict
  confirm_action    — ask yes/no before an agent takes a risky action
"""

from .human_tools import ask_human, ask_human_multi, confirm_action

__all__ = ["ask_human", "ask_human_multi", "confirm_action"]
