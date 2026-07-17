"""
core/tools/handoff/human_tools.py
───────────────────────────────────
Human-in-the-loop handoff tools.

These tools pause the swarm and collect real-time input from the user
at the terminal. Designed for conversational/interview-style agents
(agent_type = "interviewer" or "chat").

Available tools:
  ask_human        — ask the user a single focused question
  ask_human_multi  — ask a list of questions in sequence; returns {question: answer}
  confirm_action   — ask yes/no before the agent takes a risky or irreversible action
"""

import json
from langchain_core.tools import tool


# ANSI colors for nicer terminal output
_CYAN  = "\033[96m"
_BOLD  = "\033[1m"
_DIM   = "\033[2m"
_GREEN = "\033[92m"
_RESET = "\033[0m"
_YELLOW = "\033[93m"


@tool
def ask_human(question: str) -> str:
    """
    Pause swarm execution and ask the human user a single question.
    The agent's next action will be based on the user's typed response.

    Use this when you need one specific piece of information from the user,
    such as their name, a preference, or a clarification.

    Args:
        question: The question to ask the user. Be specific and concise.

    Returns:
        The user's exact typed response as a string.

    Example:
        ask_human("What is your full name?")
        → "Swapnil Jyot"
    """
    print(f"\n{_BOLD}{_CYAN}🙋 Agent Question:{_RESET}")
    print(f"  {_YELLOW}{question}{_RESET}")
    print(f"{_DIM}  (Type your answer and press Enter){_RESET}")

    answer = input(f"{_GREEN}  Your answer: {_RESET}").strip()

    print(f"{_DIM}  ✔ Answer recorded.{_RESET}\n")
    return answer if answer else "(No answer provided)"


@tool
def ask_human_multi(questions: list) -> str:
    """
    Pause swarm execution and ask the user a list of questions one by one.
    Returns all answers as a JSON string mapping each question to its answer.

    Use this to collect multiple pieces of data in a single tool call instead
    of calling ask_human repeatedly. Ideal for onboarding or intake forms.

    Args:
        questions: A list of question strings to ask in order.
                   Example: ["What is your name?", "How many years of experience do you have?"]

    Returns:
        A JSON string: {"question1": "answer1", "question2": "answer2", ...}

    Example:
        ask_human_multi([
            "What is your full name?",
            "How many years of experience do you have?",
            "What are your key skills?",
            "What is your current or last company?"
        ])
        → '{"What is your full name?": "Swapnil", ...}'
    """
    print(f"\n{_BOLD}{_CYAN}🙋 Agent has {len(questions)} question(s) for you:{_RESET}\n")

    answers = {}
    for i, question in enumerate(questions, start=1):
        print(f"  {_BOLD}[{i}/{len(questions)}]{_RESET} {_YELLOW}{question}{_RESET}")
        answer = input(f"{_GREEN}  Your answer: {_RESET}").strip()
        answers[question] = answer if answer else "(No answer provided)"
        print()

    print(f"{_DIM}  ✔ All answers recorded.{_RESET}\n")
    return json.dumps(answers, indent=2)


@tool
def confirm_action(description: str) -> str:
    """
    Ask the user to confirm before the agent takes a potentially risky or
    irreversible action (e.g., deleting data, sending emails, overwriting files).

    The agent should NOT proceed with the action unless this tool returns "confirmed".

    Args:
        description: A clear, plain-English description of what the agent is about to do.
                     Example: "Delete all records in the 'users' table for session ABC."

    Returns:
        "confirmed"  — if the user typed 'y' or 'yes'
        "cancelled"  — if the user typed 'n' or 'no' or pressed Enter without input
    """
    print(f"\n{_BOLD}{_YELLOW}⚠️  Agent wants to perform an action — your approval is required:{_RESET}")
    print(f"  {description}\n")

    response = input(f"{_GREEN}  Approve? (y/n): {_RESET}").strip().lower()

    if response in ("y", "yes"):
        print(f"{_DIM}  ✔ Action confirmed by user.{_RESET}\n")
        return "confirmed"
    else:
        print(f"{_DIM}  ✖ Action cancelled by user.{_RESET}\n")
        return "cancelled"
