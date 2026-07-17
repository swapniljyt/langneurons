"""
core/state/langneural_state.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER  : State
ROLE   : The shared state bag — the single source of truth passed between every agent invocation.

KEY CONCEPTS IN THIS FILE:
  • FileWriteData / FileEditData  (line ~11)  — Structured log of file operations agents perform
  • ToolOperationRecord           (line ~30)  — Single tool call log entry (name, args, result, timestamp)
  • TaskReceived                  (line ~70)  — The active task packet passed into each neural_agent() call
  • LangNeuralState               (line ~120) — The full LangGraph state TypedDict; contains ALL swarm state
  • team_tool_report              (in State)  — Accumulated log of ALL tool calls across all agents (never flushed)
  • team_execution_report         (in State)  — Summary of what each agent reported back to its supervisor

DEPENDS ON:
  • pydantic (BaseModel, Field)   — for structured data validation

CALLED BY:
  • core/engine/agent_factory.py  — reads/writes state on every agent turn
  • core/engine/prompt_builder.py — reads state to inject team_tool_report into system prompts
  • core/swarm.py                 — initialises the state before the first agent runs
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ==========================================
# 1. SPECIFIC FILE DATA STRUCTURES
# ==========================================
class FileWriteData(BaseModel):
    file_path: str = Field(description="The full path and name of the file created")
    description: str = Field(description="Summary of what data/code was generated")
    content: str = Field(description="The actual code or data written inside the file")

class FileEditData(BaseModel):
    file_path: str = Field(description="The path to the file that was edited")
    edit_description: str = Field(description="Description of what was edited, added, or removed in this file")

# ==========================================
# 2. TOOL ACTIONS STRUCTURES
# ==========================================
class ReadAction(BaseModel):
    timestamp: str = Field(description="ISO 8601 timestamp of when this action occurred")
    tools_used: List[str] = Field(description="e.g., ['read_file', 'parse_pdf']")
    commands_executed: List[str] = Field(default_factory=list, description="Any terminal/CLI commands executed")
    data_gathered: List[str] = Field(description="Structured bullet points of information gathered")

class WriteAction(BaseModel):
    timestamp: str = Field(description="ISO 8601 timestamp of when this action occurred")
    tools_used: List[str] = Field(description="e.g., ['create_file', 'write_code']")
    commands_executed: List[str] = Field(default_factory=list, description="Any terminal/CLI commands executed")
    files_written: List[FileWriteData] = Field(description="Structured list of files created and their contents")

class EditAction(BaseModel):
    timestamp: str = Field(description="ISO 8601 timestamp of when this action occurred")
    tools_used: List[str] = Field(description="e.g., ['modify_file', 'sed_command']")
    commands_executed: List[str] = Field(default_factory=list, description="Any terminal/CLI commands executed")
    files_edited: List[FileEditData] = Field(description="Structured list of files modified and the edits made")

class ErrorAction(BaseModel):
    timestamp: str = Field(description="ISO 8601 timestamp of when this action occurred")
    tools_used: List[str] = Field(description="e.g., ['execute_script']")
    commands_executed: List[str] = Field(default_factory=list, description="Any terminal/CLI commands executed")
    error_message: str = Field(description="What exact error you got")
    file_location: str = Field(description="From which file or path you got the error")
    reason: str = Field(description="Reason why the error occurred")

class AgentToolReport(BaseModel):
    read: List[ReadAction] = Field(default_factory=list)
    write: List[WriteAction] = Field(default_factory=list)
    edited: List[EditAction] = Field(default_factory=list)
    error: List[ErrorAction] = Field(default_factory=list)

# ==========================================
# 3. CHAIN OF COMMAND & TASKS STRUCTURE
# ==========================================
class AgentNode(BaseModel):
    supervisor: str = Field(description="The agent who delegates tasks to this agent (e.g., 'human' or 'task_coordinator')")
    subordinates: List[str] = Field(default_factory=list, description="The agents this agent can delegate tasks to")

class AssignedTask(BaseModel):
    timestamp: str = Field(default_factory=_utc_now, description="ISO 8601 timestamp of when this task was assigned")
    supervisor: str = Field(description="The name of the supervisor who assigned you this task")
    task_instructions: str = Field(description="The exact task instructions you received")
    response_provided: str = Field(default="pending", description="The final response you provided back to the supervisor")

class TaskDelegation(BaseModel):
    timestamp: str = Field(default_factory=_utc_now, description="ISO 8601 timestamp of when this task was delegated")
    subordinate_agent: str = Field(description="The agent receiving the task")
    task_delivered: str = Field(description="The exact task instructions given to the subordinate")
    task_response: str = Field(default="pending", description="The final output/response received from the subordinate")

class AgentExecutionRecord(BaseModel):
    """
    The execution inbox/outbox for a single agent within one turn.

    SEQUENTIAL EXECUTION CONTRACT:
    ─────────────────────────────────────────────────────
    Only ONE agent holds the state at a time. NO parallel execution.
    When a supervisor has multiple subordinates, it delegates to the first,
    waits for the full response, then delegates to the second, and so on.

    State access pattern:
        state.team_execution_report["BackendDeveloperAgent"].task_received
        state.team_execution_report["task_coordinator"].tasks_delegated

    task_received is a SINGLE Optional[AssignedTask] — not a list — because
    sequential execution means only one task is ever active per agent per turn.
    Full historical list of past tasks (with timestamps) lives in Redis only.
    """
    task_received: Optional[AssignedTask] = Field(
        None,
        description="The single active task this agent received from its supervisor this turn."
    )
    tasks_delegated: List[TaskDelegation] = Field(
        default_factory=list,
        description="Ordered list of tasks delegated to subordinates — executed sequentially, one at a time."
    )

# ==========================================
# 4. LLM OUTPUT DELTA
# ==========================================
class AgentUpdate(BaseModel):
    new_delegations: List[TaskDelegation] = Field(default_factory=list, description="Any tasks you delegated just now.")
    new_tool_actions: AgentToolReport = Field(default_factory=AgentToolReport, description="Any tools you used just now.")
    response_to_parent_or_user: str = Field(description="Your conversational response back to the user or delegating agent.")

# ==========================================
# 5. THE GLOBAL STATE
# ==========================================
class LangneuralState(BaseModel):
    human_prompt: str = Field(description="The original instruction from the human user")
    agent_tools: Dict[str, List[str]] = Field(description="Mapping of agent names to their available tools")
    agent_hierarchy: Dict[str, AgentNode] = Field(description="Mapping of agent names to their chain of command position")
    team_execution_report: Dict[str, AgentExecutionRecord] = Field(default_factory=dict, description="Dictionary keyed by agent name, storing their task interactions.")
    team_tool_report: Dict[str, AgentToolReport] = Field(default_factory=dict)

# ==========================================
# EXAMPLE USAGE (for reference)
# ==========================================

# {
#   "human_prompt": "Build a simple FastAPI login endpoint.",
#   "agent_tools": {
#     "task_coordinator": ["ask_human"],
#     "BackendDeveloperAgent": ["create_file", "modify_file", "run_script"],
#     "CodeReviewAgent": ["read_file", "run_pytest"]
#   },
#   "agent_hierarchy": {
#     "task_coordinator": {
#       "supervisor": "human",
#       "subordinates": [
#         "BackendDeveloperAgent",
#         "CodeReviewAgent"
#       ]
#     },
#     "BackendDeveloperAgent": {
#       "supervisor": "task_coordinator",
#       "subordinates": []
#     },
#     "CodeReviewAgent": {
#       "supervisor": "task_coordinator",
#       "subordinates": []
#     }
#   },
#   # Access pattern:
#   #   state.team_execution_report["task_coordinator"].task_received
#   #   state.team_execution_report["BackendDeveloperAgent"].task_received
#   #   state.team_execution_report["task_coordinator"].tasks_delegated
#   #
#   # Sequential contract:
#   #   task_coordinator delegates to BackendDeveloperAgent → waits for response
#   #   → then delegates to CodeReviewAgent → waits for response
#   #   → then compiles final response_provided back to human
#   "team_execution_report": {
#     "task_coordinator": {
#       "task_received": {
#         "supervisor": "human",
#         "task_instructions": "Build a simple FastAPI login endpoint.",
#         "response_provided": "The FastAPI login endpoint has been successfully built, integrated into the main application, and passed all code reviews."
#       },
#       "tasks_delegated": [
#         {
#           "subordinate_agent": "BackendDeveloperAgent",
#           "task_delivered": "Create a login endpoint in FastAPI inside the src/api directory.",
#           "task_response": "Login endpoint created and integrated into main.py successfully. Error encountered with missing dependency was resolved."
#         },
#         {
#           "subordinate_agent": "CodeReviewAgent",
#           "task_delivered": "Review the code written by BackendDeveloperAgent in src/api/routes.py and src/main.py for any issues.",
#           "task_response": "Code review complete. Implementation is clean and all tests passed."
#         }
#       ]
#     },
#     "BackendDeveloperAgent": {
#       "task_received": {
#         "supervisor": "task_coordinator",
#         "task_instructions": "Create a login endpoint in FastAPI inside the src/api directory.",
#         "response_provided": "Login endpoint created and integrated into main.py successfully. Error encountered with missing dependency was resolved."
#       },
#       "tasks_delegated": []
#     },
#     "CodeReviewAgent": {
#       "task_received": {
#         "supervisor": "task_coordinator",
#         "task_instructions": "Review the code written by BackendDeveloperAgent in src/api/routes.py and src/main.py for any issues.",
#         "response_provided": "Code review complete. Implementation is clean and all tests passed."
#       },
#       "tasks_delegated": []
#     }
#   },
#   "team_tool_report": {
#     "BackendDeveloperAgent": {
#       "read": [
#         {
#           "tools_used": ["read_file"],
#           "commands_executed": [
#             "cat requirements.txt",
#             "cat src/main.py"
#           ],
#           "data_gathered": [
#             "Read requirements.txt: Confirmed FastAPI is listed as a requirement.",
#             "Read src/main.py: Found existing database connection logic to integrate with."
#           ]
#         }
#       ],
#       "write": [
#         {
#           "tools_used": ["create_file"],
#           "commands_executed": [
#             "mkdir -p src/api",
#             "pip install fastapi uvicorn"
#           ],
#           "files_written": [
#             {
#               "file_path": "src/api/routes.py",
#               "description": "Generated user authentication endpoint for login.",
#               "content": "from fastapi import APIRouter\n\nrouter = APIRouter()\n\n@router.get('/login')\ndef login():\n    return {'status': 'success', 'message': 'Logged in'}"
#             }
#           ]
#         }
#       ],
#       "edited": [
#         {
#           "tools_used": ["modify_file"],
#           "commands_executed": [
#             "sed -i 's/app = FastAPI()/app = FastAPI()\\napp.include_router(router)/g' src/main.py"
#           ],
#           "files_edited": [
#             {
#               "file_path": "src/main.py",
#               "edit_description": "Imported the new auth router from src.api.routes and included it in the main FastAPI app instance using app.include_router(router)."
#             }
#           ]
#         }
#       ],
#       "error": [
#         {
#           "tools_used": ["run_script"],
#           "commands_executed": [
#             "python src/main.py"
#           ],
#           "error_message": "ModuleNotFoundError: No module named 'fastapi'",
#           "file_location": "src/main.py",
#           "reason": "FastAPI was not installed in the current virtual environment before running the server script. Fixed by running pip install."
#         }
#       ]
#     },
#     "CodeReviewAgent": {
#       "read": [
#         {
#           "tools_used": ["read_file", "run_pytest"],
#           "commands_executed": [
#             "cat src/api/routes.py",
#             "pytest test_routes.py -v"
#           ],
#           "data_gathered": [
#             "Read src/api/routes.py: Code structure follows standard FastAPI router conventions.",
#             "Ran pytest on test_routes.py: All 3 authentication tests passed successfully."
#           ]
#         }
#       ],
#       "write": [],
#       "edited": [],
#       "error": []
#     }
#   }
# }
