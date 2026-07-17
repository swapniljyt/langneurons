# LangNeurons — Architecture & Navigation Guide

> **New developer?** Start here. This file is your map.
> Find any concept in under 30 seconds without running code.

---

## Table of Contents

1. [Concept → File Map](#concept--file-map)
2. [Data Flow Diagram](#data-flow-diagram)
3. [Repo Layout](#repo-layout)
4. [Agent Type Cheat Sheet](#agent-type-cheat-sheet)
5. [How to Run](#how-to-run)
6. [Key Design Decisions](#key-design-decisions)

---

## Concept → File Map

| I want to find...                        | File                                          | Where inside              |
|------------------------------------------|-----------------------------------------------|---------------------------|
| **ReAct agent creation**                 | `core/engine/agent_factory.py`                | `_execute_tools()` ~L395  |
| **Thinking mode (kimi-k2.5)**            | `core/llm/connector.py`                       | `THINKING_AGENT_TYPES` ~L40 |
| **Swarm entry point**                    | `core/swarm.py`                               | `run_swarm()` ~L1         |
| **Agent tree scheduler**                 | `core/engine/orchestrator.py`                 | `Orchestrator` class ~L39 |
| **Agent data model (1 neuron)**          | `core/agents/agent_node.py`                   | `AgentNode` class ~L36    |
| **System prompt assembly**               | `core/engine/prompt_builder.py`               | `build_agent_prompt()` ~L1|
| **Skill auto-generation from brief**     | `core/modules/skill_generator.py`             | `generate_skill()` ~L50   |
| **Tool → agent mapping (registry)**      | `core/tools/registry.py`                      | `AGENT_CAPABILITY_MAP` ~L89|
| **Sandbox path enforcement**             | `core/tools/filesystem/read_write.py`         | `_get_sandboxed_path()` ~L23|
| **Namespace locking (per-agent dir)**    | `core/tools/filesystem/read_write.py`         | `_enforce_namespace()` ~L38|
| **Shell command execution**              | `core/tools/execution/runner.py`              | `execute_command()` ~L20  |
| **Agent → agent contracts (publish)**    | `core/tools/coordination/contracts.py`        | `publish_contract` tool   |
| **Shared swarm state bag**               | `core/state/langneural_state.py`              | `LangNeuralState` ~L120   |
| **team_tool_report (inter-agent log)**   | `core/state/langneural_state.py`              | `team_tool_report` field  |
| **Redis checkpointing per agent**        | `core/engine/memory.py`                       | `RedisClient` ~L1         |
| **Shared org memory (timeline)**         | `core/memory/memory.py`                       | `SharedStateStore` ~L72   |
| **Agent tree visualizer (console)**      | `core/agents/visualizer.py`                   | `Visualizer.print_tree()` |
| **Hallucination guard (tool retry)**     | `core/engine/agent_factory.py`                | `_has_tool_call()` ~L480  |
| **Swarm entry point CLI**                | `entrypoints/run_agent_langneuron.py`         | `FORMATION_BRIEF` + `build_swarm_tree()` |
| **How task is decomposed per agent**     | `core/modules/task_decomposer.py`             | `TaskDecomposer` ~L1      |
| **Which agents activate (routing)**      | `core/modules/activation_router.py`           | `ActivationRouter` ~L1    |

---

## Data Flow Diagram

```
User: "Build me an e-commerce site"
          │
          ▼
  run_swarm()                         [core/swarm.py]
          │
          ├─ UNFREEZE PATH (first run)
          │      │
          │      ▼
          │  Orchestrator._build_phase()    [core/engine/orchestrator.py]
          │      ├─ SkillGenerator    → generates .md persona per agent
          │      ├─ TaskDecomposer    → assigns subtask to each neuron
          │      └─ Saves tree to Redis (session_id key)
          │
          └─ FREEZE PATH (--freeze flag)
                 │
                 ▼
             Orchestrator._freeze_phase()  [core/engine/orchestrator.py]
                 ├─ Loads tree from Redis
                 ├─ Shows greeting (Neuron1 = task_coordinator)
                 └─ On user message:
                        │
                        ▼
                    neural_agent()          [core/engine/agent_factory.py]
                        │
                        ├─ Step A: build_agent_prompt()
                        │          [core/engine/prompt_builder.py]
                        │          Assembles 8-section system prompt from:
                        │            - skill .md file
                        │            - team directory
                        │            - team_tool_report  ← anti-context-bleed
                        │            - task_received
                        │
                        ├─ Step B: Router LLM call → AgentDecision
                        │          (delegate | use_tool | respond)
                        │
                        ├─ Step C: if delegate → recursively activate child
                        │
                        └─ Step D: if use_tool → _execute_tools()
                                   [core/engine/agent_factory.py ~L395]
                                       │
                                       ├─ Creates LangGraph ReAct agent
                                       ├─ Streams thinking to console (🧠💡)
                                       ├─ Agent calls tools (write_file, execute_command...)
                                       ├─ Hallucination guard: retries if no tool called
                                       └─ Returns report → state updated → passed upward
```

---

## Repo Layout

```
langneurons/
│
├── ARCHITECTURE.md          ← YOU ARE HERE
├── README.md                ← Quick start
├── requirements.txt
├── pyproject.toml
│
├── entrypoints/             ← START HERE when running a new swarm
│   └── run_agent_langneuron.py   ← Edit FORMATION_BRIEF + build_swarm_tree() here
│
├── core/                    ← All framework code lives here
│   ├── swarm.py             ← Public entry point: run_swarm()
│   │
│   ├── engine/              ← The execution engine
│   │   ├── agent_factory.py ← ReAct agent loop, thinking stream, hallucination guard
│   │   ├── orchestrator.py  ← Tree walker, scheduler, build/freeze phases
│   │   ├── prompt_builder.py← 8-section system prompt assembler
│   │   ├── llm_gateway.py   ← Structured LLM calls (router tier)
│   │   └── memory.py        ← Redis client wrapper
│   │
│   ├── agents/              ← Agent data model
│   │   ├── agent_node.py    ← AgentNode class (one neuron's full config)
│   │   └── visualizer.py    ← Console tree printer
│   │
│   ├── llm/
│   │   └── connector.py     ← LLM provider selector, thinking mode toggle
│   │
│   ├── state/
│   │   └── langneural_state.py  ← Shared state bag (LangNeuralState TypedDict)
│   │
│   ├── memory/
│   │   └── memory.py        ← Shared org memory (timeline, responsibilities, metadata)
│   │
│   ├── modules/             ← Build-phase intelligence
│   │   ├── skill_generator.py   ← Auto-generates agent personas from FORMATION_BRIEF
│   │   ├── task_decomposer.py   ← Breaks brief into per-agent subtasks
│   │   ├── activation_router.py ← Decides which agents are active/dormant
│   │   └── role_manager.py      ← Assigns dynamic role names to neurons
│   │
│   ├── tools/               ← All agent tools (capability-based)
│   │   ├── registry.py      ← AGENT_CAPABILITY_MAP (agent_type → tools)
│   │   ├── filesystem/      ← read_file, write_file, edit_file_patch, sandbox enforcement
│   │   ├── execution/       ← execute_command (shell runner, sandbox cwd)
│   │   ├── coordination/    ← publish_contract, read_contracts (inter-agent API specs)
│   │   ├── documents/       ← PDF generation, document parsing
│   │   ├── handoff/         ← ask_human, confirm_action (human-in-the-loop)
│   │   └── intelligence/    ← web search
│   │
│   ├── skills/
│   │   └── definitions/     ← Auto-generated .md skill files per session/agent
│   │
│   └── prompts/
│       └── system/          ← Base prompt templates (agent_prompt.md)
│
├── sandbox/                 ← ALL agent file output goes here (git-ignored)
│   ├── backend/
│   ├── frontend/
│   └── tests/
│
├── experiments/             ← Scratch notebooks and one-off scripts (git-ignored)
└── assets/                  ← Personal files, PDFs, etc. (git-ignored)
```

---

## Agent Type Cheat Sheet

| `agent_type`  | 🧠 Thinking | 💻 Shell | ✏️ Write Files | 🙋 Human I/O | Use for                          |
|---------------|:-----------:|:--------:|:--------------:|:------------:|----------------------------------|
| `chat`        |      ✗      |    ✗     |       ✗        |      ✓       | Root coordinator / task router   |
| `interviewer` |      ✗      |    ✗     |       ✗        |      ✓       | HR / Q&A / conversational agents |
| `writer`      |      ✓      |    ✗     |       ✓        |      ✗       | Code writers, doc generators     |
| `architect`   |      ✓      |    ✓     |       ✓        |      ✗       | Design + build + execute         |
| `runner`      |      ✓      |    ✓     |       ✓        |      ✗       | DevOps / QA / test / debug       |
| `researcher`  |      ✗      |    ✗     |       ✓        |      ✗       | Web search + document analysis   |
| `analyst`     |      ✓      |    ✓     |       ✗        |      ✗       | Data pipelines + shell analysis  |
| `assembler`   |      ✗      |    ✗     |       ✓        |      ✗       | Final merge agent (one output)   |

> **Thinking** = Uses Moonshot kimi-k2.5 with `thinking=True`. Streams reasoning to console as `🧠💡`.
> **Shell** = Has access to `execute_command` tool (runs inside `sandbox/` cwd).
> **Write Files** = Has access to `write_file`, `create_directory`, `edit_file_patch`.

---

## How to Run

```bash
# Step 1 — Build the swarm (generates agent skills, saves tree to Redis)
python entrypoints/run_agent_langneuron.py

# Step 2 — Run the swarm (loads tree, starts chat)
python entrypoints/run_agent_langneuron.py --freeze

# Step 3 — Fresh start (clears execution history, keeps tree)
python entrypoints/run_agent_langneuron.py --freeze --clean-memory

# Tip: Use --cache to skip skill re-generation if FORMATION_BRIEF is unchanged
python entrypoints/run_agent_langneuron.py --cache
```

**To configure a new swarm**, open `entrypoints/run_agent_langneuron.py` and edit:
1. `SESSION_NAME` — unique Redis key for this swarm
2. `FORMATION_BRIEF` — plain language description of what the swarm should do
3. `build_swarm_tree()` — define agents and hierarchy with `AgentNode` + `.add_child()`

---

## Key Design Decisions

| Decision | Why |
|---|---|
| **Two LLM tiers** (router + execution) | Router uses cheap/fast LLM for structured delegation. Execution uses kimi-k2.5 with thinking for complex reasoning. |
| **Thinking mode is selective** | Only `architect`, `analyst`, `runner`, `writer` use thinking. Router NEVER uses thinking (incompatible with `with_structured_output`). |
| **team_tool_report never flushes** | Every tool call is logged forever so agents always know what previous agents did. Prevents duplicate work. |
| **Sandbox + namespace locking** | Agents can only write inside `sandbox/`. Each agent is further restricted to its own sub-directory (e.g. `backend/`). |
| **Thread-isolated checkpointing** | Each agent uses `thread_id = session_id::agent_name`. LangGraph memory is 100% isolated per agent — no context bleed. |
| **Hallucination guard** | After every ReAct loop, the system checks if at least one tool was actually called. If not, it retries up to 2 times with an escalation warning. |
| **publish_contract / read_contracts** | Agents communicate API specs as structured JSON contracts (not chat messages) so downstream agents build to a guaranteed interface. |
