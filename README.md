<p align="center">
  <img src="./backend/assets/logo.png" alt="LangNeurons Logo" width="520"/>
</p>

<p align="center">
  <strong>Production-grade hierarchical multi-agent swarm framework built on LangGraph.</strong><br/>
  Decompose any task into a tree of intelligent agents — each with isolated memory, selective thinking, and capability-locked tools.
</p>

<p align="center">
  <a href="#-quick-start"><img src="https://img.shields.io/badge/quick%20start-→-2ea44f?style=for-the-badge" alt="Quick Start"/></a>
  <a href="#-architecture"><img src="https://img.shields.io/badge/architecture-→-5b8dee?style=for-the-badge" alt="Architecture"/></a>
  <a href="#-agent-types"><img src="https://img.shields.io/badge/agent%20types-→-8b5cf6?style=for-the-badge" alt="Agent Types"/></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/LangGraph-0.3+-1C3C5A?logo=langchain&logoColor=white" alt="LangGraph"/>
  <img src="https://img.shields.io/badge/Redis-Persistent%20Memory-DC382D?logo=redis&logoColor=white" alt="Redis"/>
  <img src="https://img.shields.io/badge/License-BUSL--1.1-orange" alt="BUSL 1.1 License"/>
  <img src="https://img.shields.io/badge/version-0.2.0-blue" alt="Version"/>
</p>

---

## What is LangNeurons?

**LangNeurons** is a framework for building **hierarchical multi-agent swarms** — fleets of AI agents organized as a tree, where each node (a "neuron") is an autonomous agent with its own:

- **Skill** — auto-generated system prompt derived from your `FORMATION_BRIEF`
- **Task** — a decomposed subtask assigned by its supervisor agent
- **Tool set** — capability-locked to its role (`writer`, `runner`, `architect`, etc.)
- **Memory** — thread-isolated Redis checkpoint with no context bleed between agents

Swarms can **build full-stack apps, conduct HR interviews, run research pipelines, generate reports, and more** — all from a single plain-language brief. No manual prompt engineering per agent required.

---

## 🚀 What Can You Build?

### 🖥️ Personalized AI Code Editor

> **Turn LangNeurons into your own intelligent, agent-powered development environment.**

LangNeurons can power a **fully personalized AI code editor** where every part of your development workflow is handled by a dedicated specialist agent — collaborating silently in the background, just like a real engineering team.

| **Feature** | **What It Does** |
|---|---|
| **🧠 Architect Agent** | Reads your intent, designs the file structure and API contracts before any code is written |
| **✍️ Writer Agents** | Each agent owns one module — `backend/`, `frontend/`, `tests/` — and writes production-quality code autonomously |
| **🔍 Reviewer Agent** | Reads all written code, checks for bugs, style violations, and missing edge cases |
| **🏃 Runner Agent** | Executes shell commands — installs deps, runs the server, runs test suites — and reports back |
| **🌐 Browser Audit Agent** | Visually inspects the running UI using Vision AI, flags layout issues, alignment bugs, and console errors |
| **📝 Assembler Agent** | Merges all outputs into a final clean codebase — one source of truth |
| **💬 Human Handoff** | Agents ask you only when genuinely blocked — zero unnecessary interruptions |

```python
# One brief. One command. A full app built by your agent team.
FORMATION_BRIEF = "Build a production FastAPI + React e-commerce app with auth, cart, and payments."
await run_swarm(prompt=FORMATION_BRIEF, freeze_mode=False, session_id="my_editor")
```

---

### 🏢 Your Own Company of Agents

> **Hire a full team of AI specialists — each with a defined role, memory, and chain of command.**

LangNeurons lets you define a **virtual organisation** of agents that collaborate like real employees — with clear reporting lines, task delegation, and inter-agent communication via structured contracts.

| **Role** | **Agent Type** | **What They Do** |
|---|---|---|
| **👔 CEO / Coordinator** | `chat` | Receives the brief from you, delegates to division leads, presents the final report |
| **🏗️ Lead Architect** | `architect` | Designs the system, publishes API contracts for the team to follow |
| **💻 Backend Engineers** | `writer` | Build APIs, databases, and business logic inside their own namespace |
| **🎨 Frontend Engineers** | `writer` | Build the UI — styled, responsive, beautiful — reading from backend contracts |
| **⚙️ DevOps Engineer** | `runner` | Writes Dockerfiles, runs builds, deploys services, fixes CI failures |
| **🧪 QA Engineer** | `runner` | Writes and runs automated tests, generates test reports |
| **🔎 Researcher** | `researcher` | Searches the web, parses documents, delivers findings to the team |
| **📊 Analyst** | `analyst` | Runs data pipelines, shell analysis, and generates insights |
| **📋 Assembler** | `assembler` | Integrates all outputs into a single final deliverable |

**Key collaborative features:**

- 🔗 **`publish_contract`** — Agents publish typed API specs so every downstream agent builds to the same interface
- 📋 **`team_tool_report`** — Every tool call is logged in a shared ledger visible to all agents — no duplicate work
- 🏗️ **Execution Stages** — Producers (backend) run first, consumers (frontend) run after — guaranteed ordering
- 🧵 **Thread-Isolated Memory** — Each agent has its own Redis checkpoint; zero context bleed between team members
- 👁️ **Full Visibility** — The coordinator always knows what every agent did, built, or reported

```python
# Define your company org chart in code
ceo        = AgentNode("Neuron1").set_agent_type("chat")
architect  = AgentNode("Neuron2").set_agent_type("architect")
backend    = AgentNode("Neuron3").set_agent_type("writer")
frontend   = AgentNode("Neuron4").set_agent_type("writer")
devops     = AgentNode("Neuron5").set_agent_type("runner")
qa         = AgentNode("Neuron6").set_agent_type("runner")

ceo.add_child(architect)
ceo.add_child(backend)
ceo.add_child(frontend)
ceo.add_child(devops)
ceo.add_child(qa)

# Your company is ready. Give them a task.
await run_swarm(prompt="Build and ship a production SaaS app.", freeze_mode=False)
```

---

## ✨ Core Features

| Feature | Description |
|---|---|
| 🧠 **Auto Skill Generation** | LLM reads your `FORMATION_BRIEF` and writes a full system prompt + role for every agent |
| 🌲 **Hierarchical Tree Execution** | Agents form a supervisor → subordinate tree; tasks flow down, results flow up |
| 🔒 **Capability-Locked Tools** | Each agent type (`writer`, `runner`, `architect`…) gets only the tools it needs |
| 📁 **Namespace Enforcement** | `writer` agents are hard-locked to their own `sandbox/<dir>/` — no cross-agent file pollution |
| 🧩 **`publish_contract` / `read_contracts`** | Agents exchange structured JSON API specs (not chat) so downstream agents build to a guaranteed interface |
| 🔄 **Two-Phase Protocol** | **Build phase** (skill gen + tree → Redis) → **Freeze phase** (load tree → chat loop) |
| 💾 **Redis Persistence** | Full tree, agent roles, tool ledger, and execution history saved across sessions |
| 🛡️ **Hallucination Guard** | After each ReAct loop, verifies at least one tool was called; retries up to 2× with escalation |
| 🧠 **Selective Thinking Mode** | `architect`, `runner`, `writer`, `analyst` use Moonshot kimi-k2.5 with streaming reasoning (`🧠💡`) |
| 📋 **`team_tool_report`** | Persistent log of every tool call across all agents — never flushed, prevents duplicate work |
| ⚡ **`--cache` Mode** | Skip skill re-generation if `FORMATION_BRIEF` is unchanged (SHA-256 hash comparison) |
| 🌐 **Multi-Provider LLM** | OpenRouter, Moonshot, Anthropic, OpenAI, Google Gemini, AWS Bedrock — switch via `.env` |
| 🖥️ **Rich Console UI** | Live tree visualization, streaming agent thinking, task assignment animations |

---

## 🏗️ Architecture

```
User Prompt ("Build an e-commerce site")
            │
            ▼
      run_swarm()                           [core/swarm.py]
            │
   ┌────────┴──────────┐
   │                   │
BUILD PHASE         FREEZE PHASE
(unfreeze)          (--freeze)
   │                   │
   ▼                   ▼
Orchestrator        Load tree from Redis
   ├─ SkillGenerator  → .md persona per agent
   ├─ TaskDecomposer  → subtask per neuron
   ├─ ActivationRouter→ active vs dormant
   └─ Save to Redis
                       │
                       ▼
                 neural_agent()            [core/engine/agent_factory.py]
                       │
              ┌────────┴─────────────────────┐
              │         │                    │
         delegate    use_tool            respond
              │         │
              ▼         ▼
      recurse child  LangGraph ReAct loop
                       ├─ build_agent_prompt()
                       │   (8-section system prompt)
                       ├─ Router LLM → AgentDecision
                       ├─ Streams thinking 🧠💡
                       ├─ Calls tools (write_file, execute_command…)
                       ├─ Hallucination guard (retry if no tool called)
                       └─ Result → state → passed upward
```

### Two LLM Tiers

| Tier | Purpose | Provider | Thinking |
|---|---|---|---|
| **Router** | Structured delegation decisions (`delegate` / `use_tool` / `respond`) | Fast/cheap (Moonshot) | ❌ Never (incompatible with structured output) |
| **Execution** | Tool-calling ReAct agent loop | Moonshot kimi-k2.5 | ✅ Selective (by `agent_type`) |

---

## 📁 Repo Layout

```
langneurons/
│
├── entrypoints/                  ← Start here for new swarms
│   └── run_agent_langneuron.py  ← Edit FORMATION_BRIEF + build_swarm_tree()
│
├── core/                         ← All framework code
│   ├── swarm.py                  ← Public entry: run_swarm()
│   │
│   ├── engine/
│   │   ├── agent_factory.py      ← ReAct loop, hallucination guard, thinking stream
│   │   ├── orchestrator.py       ← Tree scheduler, build/freeze phases
│   │   ├── prompt_builder.py     ← 8-section system prompt assembler
│   │   ├── llm_gateway.py        ← Structured LLM calls (router tier)
│   │   └── memory.py             ← Redis client wrapper
│   │
│   ├── agents/
│   │   ├── agent_node.py         ← AgentNode class (one neuron's full config)
│   │   └── visualizer.py         ← Console tree printer
│   │
│   ├── llm/
│   │   └── connector.py          ← Provider selector, thinking mode toggle
│   │
│   ├── state/
│   │   └── langneural_state.py   ← LangneuralState TypedDict (shared state bag)
│   │
│   ├── memory/
│   │   └── memory.py             ← Shared org memory (timeline, responsibilities)
│   │
│   ├── modules/
│   │   ├── skill_generator.py    ← Auto-generates agent personas from FORMATION_BRIEF
│   │   ├── task_decomposer.py    ← Assigns subtasks to each neuron
│   │   ├── activation_router.py  ← Decides active vs dormant agents per turn
│   │   └── role_manager.py       ← Assigns dynamic role names to neurons
│   │
│   └── tools/
│       ├── registry.py           ← AGENT_CAPABILITY_MAP (agent_type → tools)
│       ├── filesystem/           ← read_file, write_file, edit_file_patch, sandbox enforcement
│       ├── execution/            ← execute_command (shell runner, sandboxed cwd)
│       ├── coordination/         ← publish_contract, read_contracts
│       ├── documents/            ← PDF generation, document parsing
│       ├── handoff/              ← ask_human, confirm_action
│       └── intelligence/         ← web search
│
└── sandbox/                      ← ALL agent file output goes here (git-ignored)
    ├── backend/
    ├── frontend/
    └── tests/
```

---

## 🤖 Agent Types

Each agent type maps to a fixed set of capability tags, which determines exactly which tools it receives at runtime.

| `agent_type` | 🧠 Thinking | 💻 Shell | ✏️ Write Files | 🙋 Human I/O | 🔍 Web Search | Best For |
|---|:-:|:-:|:-:|:-:|:-:|---|
| `chat` | ✗ | ✗ | ✗ | ✓ | ✗ | Root coordinator / task router |
| `interviewer` | ✗ | ✗ | ✗ | ✓ | ✗ | HR / Q&A / conversational flows |
| `writer` | ✓ | ✗ | ✓ | ✗ | ✗ | Code writers, doc generators |
| `architect` | ✓ | ✓ | ✓ | ✗ | ✗ | System design + build + execute |
| `runner` | ✓ | ✓ | ✓ | ✗ | ✗ | DevOps / QA / testing / debugging |
| `researcher` | ✗ | ✗ | ✓ | ✗ | ✓ | Web search + document analysis |
| `analyst` | ✓ | ✓ | ✗ | ✗ | ✗ | Data pipelines + shell analysis |
| `assembler` | ✗ | ✗ | ✓ | ✗ | ✗ | Final merge agent (one output) |

> **Thinking** = Moonshot kimi-k2.5 with `thinking=True`. Streams visible reasoning to console as `🧠💡`.
> **Namespace locking** = `writer` + `assembler` agents are restricted to their assigned `sandbox/<dir>/`.

---

## ⚡ Quick Start

### 1. Install & Setup (One-Command Setup)

Simply clone the repository and run the setup script. It automatically verifies Python, installs virtual environment dependencies, installs/starts Redis server, and prepares your `.env` template:

```bash
git clone https://github.com/swapniljyt/langneurons.git
cd langneurons
./setup.sh
```

### 2. Configure

Create a `.env` file in the `langneurons/` root:

```dotenv
# ── LLM Provider (pick one) ───────────────────────────────────────
LLM_PROVIDER=moonshot          # moonshot | openrouter | openai | anthropic | google | bedrock

# Moonshot (default, recommended — supports thinking mode)
MOONSHOT_API_KEY=sk-...

# OpenRouter (access 100+ models)
# OPENROUTER_API_KEY=sk-or-...

# OpenAI
# OPENAI_API_KEY=sk-proj-...

# Anthropic Claude
# ANTHROPIC_API_KEY=sk-ant-...

# Google Gemini
# GEMINI_API=AIza...

# ── Redis ──────────────────────────────────────────────────────────
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=                # leave blank if no auth

# ── Web Search (optional, for researcher agents) ───────────────────
TAVILY_API_KEY=tvly-...

# ── Debug (optional) ──────────────────────────────────────────────
LANGNEURONS_VERBOSE=1          # prints tool assignments per agent
```

### 4. Configure Your Swarm

Open `entrypoints/run_agent_langneuron.py` and edit three things:

**① Session Name** — unique Redis key for this swarm:
```python
SESSION_NAME = "my_project_session"
```

**② Formation Brief** — plain language description of what the swarm should do:
```python
FORMATION_BRIEF = """
You are a research swarm. Your mission is to research the latest advancements
in quantum computing and produce a comprehensive report.

WORKFLOW:
  Phase 1 — Web Research: Search for papers, articles, and breakthroughs.
  Phase 2 — Analysis: Identify key themes and rank by impact.
  Phase 3 — Report Writing: Produce a styled PDF report in docs/report.md.

RULES:
  - Always cite sources.
  - The report must be professional and structured.
"""
```

**③ Swarm Tree** — define the agent hierarchy:
```python
def build_swarm_tree() -> AgentNode:
    root       = AgentNode("Neuron1", session_id=SESSION_NAME)  # coordinator
    researcher = AgentNode("Neuron2", session_id=SESSION_NAME)  # web search
    analyst    = AgentNode("Neuron3", session_id=SESSION_NAME)  # analysis
    writer     = AgentNode("Neuron4", session_id=SESSION_NAME)  # report writing

    root.add_child(researcher)
    root.add_child(analyst)
    root.add_child(writer)
    return root
```

### 3. Run

LangNeurons offers two ways to interact with your agent swarms: via the interactive visual console, or strictly through the backend CLI.

#### Option A: Visual Console (Recommended)

To use the interactive **Swarm Brain Engine Console**, run the orchestrator backend and the frontend in separate terminal windows.

**Terminal 1: Start the Backend Orchestrator**
```bash
./run.sh
```

**Terminal 2: Start the Frontend Console**
```bash
cd frontend
python3 server.py
```
Open your browser to **[http://localhost:8000](http://localhost:8000)** to access the visual dashboard!

---

#### Option B: Backend CLI Mode

If you prefer to build and explore your swarms directly in the terminal without a UI, you can run the backend engine directly.

```bash
# Step 1 — Build Phase: Generate skills, allocate subtasks, save tree to Redis
backend/venv/bin/python3 backend/entrypoints/run_agent_langneuron.py

# Step 2 — Execution Phase: Load tree, activate agents, and start the swarm
backend/venv/bin/python3 backend/entrypoints/run_agent_langneuron.py --freeze

# Tip: Reset execution memory but keep the generated tree structure
backend/venv/bin/python3 backend/entrypoints/run_agent_langneuron.py --freeze --clean-memory
```

**📊 Tracking Conversations & LangTrace (Cost Analytics)**

LangNeurons features a built-in **LangTrace** interceptor that automatically tracks every LLM call across your swarm. It calculates exact token usage and financial cost in real-time, storing it in Redis (`langtrace:{session_id}:calls`). 

This tracks:
- **Input/Output Tokens** per agent
- **Cost breakdown** (e.g., how much the `architect` spent vs the `writer`)
- **System Prompt Overhead** (skeleton tokens vs skill tokens)

If you are using the Frontend Console, this data is automatically visualized in the Telemetry tab. If you are using the Backend CLI, you can view the live thought processes and cost analytics by running:

```bash
# View live agent thoughts and LangTrace cost metrics
backend/venv/bin/python3 backend/tests/monitor_conversations.py
```

---

## 🔌 Using the Python API

```python
import asyncio
from core import run_swarm, AgentNode

SESSION = "my_app_session"

def build_tree():
    root    = AgentNode("Neuron1", session_id=SESSION)
    backend = AgentNode("Neuron2", session_id=SESSION)
    frontend= AgentNode("Neuron3", session_id=SESSION)
    runner  = AgentNode("Neuron4", session_id=SESSION)

    # Manually set agent types (optional — LLM infers from subtask if not set)
    backend.set_agent_type("writer")
    frontend.set_agent_type("writer")
    runner.set_agent_type("runner")

    # Optional per-agent behavioral tuning
    backend.set_behavior_hint("Always use FastAPI. Write clean, documented code.")
    frontend.set_behavior_hint("Use glassmorphism UI with vibrant colors.")

    root.add_child(backend)
    root.add_child(frontend)
    root.add_child(runner)
    return root

BRIEF = "Build a REST API with a beautiful frontend and run integration tests."

async def main():
    # Phase 1: Build tree and generate skills
    await run_swarm(
        prompt=BRIEF,
        freeze_mode=False,          # build phase
        custom_tree=build_tree(),
        session_id=SESSION,
    )

    # Phase 2: Execute
    await run_swarm(
        prompt=BRIEF,
        freeze_mode=True,           # execution phase
        custom_tree=build_tree(),
        session_id=SESSION,
        thinking_mode=True,         # enable kimi-k2.5 thinking
    )

asyncio.run(main())
```

### Advanced: Custom Tools & Agent Types

```python
from langchain_core.tools import tool
from core.tools.registry import register_tool, register_agent_type

# Register a custom tool
@tool
def query_database(sql: str) -> str:
    """Execute a SQL query and return results."""
    ...

register_tool(query_database, capabilities=["sql_read"])

# Register a new agent type that uses it
register_agent_type("data_scientist", capabilities=["sql_read", "shell_execution", "file_write"])

# Now any node with .set_agent_type("data_scientist") gets query_database
```

---

## 🔑 Key Design Decisions

| Decision | Rationale |
|---|---|
| **Two LLM tiers** | Router uses cheap/fast LLM for structured delegation. Execution uses kimi-k2.5 with thinking for complex reasoning. |
| **Thinking mode is selective** | Only `architect`, `analyst`, `runner`, `writer` use thinking. Router NEVER uses thinking — incompatible with `with_structured_output`. |
| **`team_tool_report` never flushes** | Every tool call is logged forever so agents always know what previous agents did. Prevents duplicate work. |
| **Sandbox + namespace locking** | Agents can only write inside `sandbox/`. Each `writer` is further restricted to its own sub-directory. |
| **Thread-isolated Redis checkpointing** | Each agent uses `thread_id = session_id::agent_name`. LangGraph memory is 100% isolated per agent — no context bleed. |
| **Hallucination guard** | After every ReAct loop, verifies at least one tool was actually called. If not, retries up to 2× with an escalation warning. |
| **`publish_contract` / `read_contracts`** | Agents communicate API specs as structured JSON (not chat messages) so downstream agents build to a guaranteed interface. |
| **`--cache` mode** | SHA-256 hash of `FORMATION_BRIEF` is stored in Redis. Identical brief = skip skill regeneration entirely. |
| **`behavior_hint`** | Per-agent persona tuning string injected into skill generation — refines tone/style without polluting the global brief. |

---

## 🧰 Tool Reference

| Tool | Capability Tag | Available To |
|---|---|---|
| `read_file` | `file_read` | All except `chat`, `interviewer` |
| `write_file` | `file_write` | `writer`, `architect`, `runner`, `assembler` |
| `create_directory` | `file_write` | `writer`, `architect`, `runner`, `assembler` |
| `edit_file_patch` | `file_read`, `file_write` | `writer`, `architect`, `runner`, `assembler` |
| `execute_command` | `shell_execution` | `architect`, `runner`, `analyst` |
| `publish_contract` | `coordination` | `writer`, `architect`, `runner`, `assembler`, `researcher` |
| `read_contracts` | `coordination` | `writer`, `architect`, `runner`, `assembler`, `researcher` |
| `ask_human` | `human_interaction` | `chat`, `interviewer` |
| `perform_web_search` | `web_search` | `researcher` |
| `browser_vision_audit` | `web_audit` | `writer`, `architect`, `runner` |
| `parse_pdf` / `parse_docx` | `document_parsing` | `researcher`, `interviewer` |
| `generate_styled_pdf_from_md` | `styled_output` | `writer` |

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## 🗺️ Concept → File Map

| Looking for... | File | Where |
|---|---|---|
| ReAct agent creation | `core/engine/agent_factory.py` | `_execute_tools()` ~L395 |
| Thinking mode config | `core/llm/connector.py` | `THINKING_AGENT_TYPES` ~L40 |
| Swarm entry point | `core/swarm.py` | `run_swarm()` ~L88 |
| Agent tree scheduler | `core/engine/orchestrator.py` | `Orchestrator` class ~L40 |
| Agent data model | `core/agents/agent_node.py` | `AgentNode` class ~L37 |
| System prompt assembly | `core/engine/prompt_builder.py` | `build_agent_prompt()` |
| Skill auto-generation | `core/modules/skill_generator.py` | `generate_skill()` ~L50 |
| Tool → agent mapping | `core/tools/registry.py` | `AGENT_CAPABILITY_MAP` ~L129 |
| Namespace enforcement | `core/tools/filesystem/read_write.py` | `_get_sandboxed_path()` |
| Shell execution | `core/tools/execution/runner.py` | `execute_command()` |
| Inter-agent contracts | `core/tools/coordination/contracts.py` | `publish_contract` |
| Shared swarm state | `core/state/langneural_state.py` | `LangneuralState` ~L135 |
| Redis checkpointing | `core/engine/memory.py` | `RedisClient` |

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Follow existing code patterns and add docstrings
4. Run tests before submitting (`pytest tests/ -v`)
5. Open a Pull Request with a clear description

---

## 📄 License

LangNeurons is licensed under the **[Business Source License 1.1 (BUSL-1.1)](./LICENSE)**.

| You CAN | You CANNOT |
|---|---|
| ✅ Read and study the code | ❌ Use commercially without permission |
| ✅ Run locally for personal/research use | ❌ Build a competing commercial product |
| ✅ Contribute via Pull Requests | ❌ Redistribute or resell |
| ✅ Fork for non-commercial work | ❌ Sublicense or white-label |

> On **January 1, 2028**, this license converts to MIT (fully open source).
>
> For commercial licensing: **swapniljytkd888@gmail.com**

© 2025 Swapnil Jyot. **LangNeurons** and the LangNeurons logo are trademarks of Swapnil Jyot.

---

<p align="center">
  Built with 🧠 by <a href="https://github.com/swapniljyt">Swapnil Jyot</a>
</p>
