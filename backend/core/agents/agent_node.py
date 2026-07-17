"""
core/agents/agent_node.py
━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER  : Agent
ROLE   : The AgentNode data model — represents one neuron in the swarm tree.

KEY CONCEPTS IN THIS FILE:
  • AgentNode class           (line ~34)  — Holds all config for one agent (type, skills, tools, namespace)
  • .set_agent_type()         (line ~194) — Locks the agent to a capability tier (writer/runner/architect...)
  • .set_behavior_hint()      (line ~216) — Optional per-agent persona tuning injected into skill generation
  • .initialize_agent()       (line ~80)  — Resolves tools via registry + instantiates the LangChain agent
  • namespace locking         (line ~95)  — Prevents agents from writing outside their assigned directory
  • .activate()               (line ~320) — Entry point called by the Orchestrator to run this agent's task

DEPENDS ON:
  • core/engine/agent_factory.py    — builds and runs the actual ReAct agent loop
  • core/tools/registry.py          — maps agent_type → allowed tools
  • core/engine/memory.py           — Redis client for checkpointing

CALLED BY:
  • core/engine/orchestrator.py     — schedules and activates nodes during freeze phase
"""

import json
from ..engine.memory import RedisClient

# Initialize Redis (module level or inside class?)
# In the original, it was module level. Let's keep it clean.
# We will initialize it when needed or keep a global instance if connections are expensive.
# The original had `redis_instance = RedisClient(); redis_client = redis_instance.get_client()` at module level.

redis_instance = RedisClient()
redis_client = redis_instance.get_client()

from ..engine.agent_factory import AgentFactory

class AgentNode:
    def __init__(self, common_name, assigned_name="", activate_flag=True, session_id="default"):
        self.original_task = ""
        self.subtask_provided = ""
        self.responsibility_domain = ""
        self.common_name = common_name
        self.dynamic_name = assigned_name
        self.session_id = session_id
        self._system_prompt = ""
        self.is_custom_prompt = False
        self.custom_persona = ""
        self.activate_flag = activate_flag
        self.context_keyvalue = []
        self.children = []
        self.parent = None
        self.agent = None  # LangChain agent instance
        self.skills = []   # List of Skill objects (Phase 3)
        self.model = None
        self.tools = []
        self.module_name = ""  # Functional module domain (e.g., "frontend", "backend")
                               # Used by ContextPacketBuilder to filter SEI interface_registry
        self.execution_stage = 0  # Build stage: 0=producers (backend/data), 1=consumers (frontend),
                                  # 2=integrators (devops/testing). Set by orchestrator from
                                  # task decomposition result. Persisted to Redis.
        self.agent_type = "writer"  # Domain-agnostic classification (set in build_tree OR auto-inferred):
                                    #   "writer"    — creates source files (isolated namespace)
                                    #   "runner"    — executes commands only (no namespace restriction)
                                    #   "assembler" — reads fragments, writes ONE file at a fixed path
        self.thread_id = f"thread_{self.session_id}_{self.common_name}" # Unique thread ID for memory
        self.retry_count = 0
        self.max_retries = 3
        self.past_failures = []
        # Optional per-agent behavioral tuning string.
        # Set via .set_behavior_hint("...") in build_swarm_tree().
        # Injected into skill generation as user_instruction.
        # Does NOT override FORMATION_BRIEF — it refines/constrains the agent's style.
        self.behavior_hint: str | None = None

    @property
    def system_prompt(self):
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, value):
        if not self._system_prompt and value:
            self.is_custom_prompt = True
            self.custom_persona = value
        self._system_prompt = value

    def initialize_agent(self, model_name: str = None, tools: list = None):
        """
        Initializes the LangChain agent for this neuron using the current system_prompt.
        """
        self.model = model_name or "moonshot/kimi-k2.5"
        if tools is None:
            tools = []

        # ── Auto-detect namespace from subtask string ──────────────────────────
        namespace = self._extract_namespace_from_subtask()
        # CRITICAL: Persist the namespace on the node so the ErrorRouter can
        # do tree-walk ownership lookups (getattr(node, "namespace", None)).
        self.namespace = namespace
        if namespace:
            print(f"🔒 [{self.common_name}] Namespace locked to: {namespace}")

        try:
            # ── Step 1: Build the full tool pool ──────────────────────────────
            from ..tools.filesystem.read_write  import read_file, write_file
            from ..tools.filesystem.directory   import create_directory, list_directory
            from ..tools.filesystem.search      import search_codebase, edit_file_patch
            from ..tools.filesystem.manifest    import list_manifest
            from ..tools.coordination.contracts import publish_contract, read_contracts
            from ..tools.execution.runner       import execute_command, create_runner_tools
            from ..tools.execution.browser_audit import browser_vision_audit
            from ..tools.execution.whatsapp     import send_whatsapp_web_message, whatsapp_user_chat
            from ..tools.handoff.human_tools    import ask_human, ask_human_multi, confirm_action
            from ..tools.documents.parser_tools import upload_document, parse_pdf, parse_docx, parse_text_file
            from ..tools.documents.pdf_generator        import generate_pdf_from_md
            from ..tools.documents.styled_pdf_generator import generate_styled_pdf_from_md
            from ..tools.intelligence.web_search_tools  import perform_web_search

            runner_tools = create_runner_tools(self.session_id)  # session-scoped suggest_fix

            full_tool_pool = [
                # Filesystem
                read_file, write_file, create_directory, list_directory,
                search_codebase, edit_file_patch, list_manifest,
                # Coordination
                publish_contract, read_contracts,
                # Execution
                execute_command, browser_vision_audit, send_whatsapp_web_message, whatsapp_user_chat,
                # Human Handoff
                ask_human, ask_human_multi, confirm_action,
                # Documents
                upload_document, parse_pdf, parse_docx, parse_text_file,
                generate_pdf_from_md, generate_styled_pdf_from_md,
                # Web Search
                perform_web_search,
            ] + runner_tools  # adds session-scoped suggest_fix

            # ── Step 2: Registry-driven filtering ─────────────────────────────
            from ..tools.registry import resolve_tools_for_agent
            resolved = resolve_tools_for_agent(self.agent_type, full_tool_pool)

            # Merge caller-provided tools first, then resolved tools (no duplicates)
            existing_names = {t.name for t in tools}
            for t in resolved:
                if t.name not in existing_names:
                    tools.append(t)
                    existing_names.add(t.name)

            import os
            if os.environ.get("LANGNEURONS_VERBOSE"):
                print(
                    f"🧰 [{self.common_name}] agent_type='{self.agent_type}' "
                    f"→ {len(tools)} tools assigned: {[t.name for t in tools]}"
                )

            # ── Step 3: Namespace enforcement for writer/assembler agents ──────
            # If namespace present, swap global write_file + create_directory
            # for hard-locked namespaced versions.
            if self.agent_type in ("writer", "assembler") and namespace:
                from ..tools.filesystem.namespaced import create_namespaced_tools
                ns_tools = create_namespaced_tools(
                    namespace=namespace,
                    agent_name=self.dynamic_name or self.common_name,
                )
                tools = [t for t in tools if t.name not in ("write_file", "create_directory")]
                tools.extend(ns_tools)
                if os.environ.get("LANGNEURONS_VERBOSE"):
                    print(f"🔒 [{self.common_name}] write_file & create_directory → namespace-locked to `{namespace}`")
            elif self.agent_type == "runner":
                if os.environ.get("LANGNEURONS_VERBOSE"):
                    print(f"🏃 [{self.common_name}] Runner — unrestricted sandbox access")

        except ImportError as e:
            print(f"⚠️ Tool registry import failed: {e}")

        # ── Step 4: Inject skills tool (always last) ──────────────────────────
        if self.skills:
            from ..skills.skill_tool import create_load_skill_tool
            load_skill_tool = create_load_skill_tool(self.skills)
            if not any(t.name == load_skill_tool.name for t in tools):
                tools.append(load_skill_tool)
                if os.environ.get("LANGNEURONS_VERBOSE"):
                    print(f"🔧 Injected {load_skill_tool.name} tool into {self.common_name}")

        current_prompt = self.system_prompt or "You are a helpful AI assistant."

        # Store tools on the node so the execution layer can access them
        self.tools = tools

        self.agent = AgentFactory.create_agent(
            system_prompt=current_prompt,
            model_name=model_name,
            tools=tools,
        )
        if os.environ.get("LANGNEURONS_VERBOSE"):
            print(f"🤖 Agent initialized for {self.common_name} ({self.dynamic_name}){' [ns:'+namespace+']' if namespace else ''}")

    def set_agent_type(self, agent_type: str) -> "AgentNode":
        """
        Manually set the agent_type. Call this in build_tree() for known roles.
        Manual setting always wins over LLM-inferred agent_type.
        Returns self for chaining: node.set_agent_type("runner")

        Types:
            "writer"    — creates source files in an isolated namespace directory
            "runner"    — executes commands (npm, docker, pytest); no namespace restriction
            "assembler" — reads all team output; writes ONE final file at a fixed path
        """
        from ..tools.registry import AGENT_CAPABILITY_MAP
        valid_types = list(AGENT_CAPABILITY_MAP.keys())
        assert agent_type in valid_types, (
            f"agent_type must be one of {valid_types}. Got: '{agent_type}'"
        )
        self.agent_type = agent_type
        self._agent_type_manually_set = True  # prevents orchestrator from overriding
        return self

    def set_behavior_hint(self, hint: str) -> "AgentNode":
        """
        Set a per-agent behavioral tuning string.
        This is injected directly into the agent's generated skill prompt.
        Use this to refine the agent's tone, style, or specific constraints
        without needing to write a massive global FORMATION_BRIEF.

        Returns self for chaining: node.set_behavior_hint("Always speak like a pirate.")
        """
        self.behavior_hint = hint
        return self

    def _extract_namespace_from_subtask(self) -> str:
        """
        Parses subtask_provided to extract assigned namespace and auto-infer agent_type.

        Namespace: looks for 'restricted to the `path/` directory' pattern.
        agent_type inference (only if not manually set via set_agent_type()):
          - Root node (no parent) is ALWAYS a supervisor — never inferred as runner
          - Subtask contains command-execution signals → "runner"
          - Subtask contains assembly/integration signals → "assembler"
          - Otherwise → "writer" (default)
        """
        import re
        text = self.subtask_provided or ""

        # ── Auto-infer agent_type from subtask content (LLM-inferred path) ────────
        # GUARD: Root node is always a supervisor — it can't be a runner even if
        # the MASTER_PROMPT contains npm/command references. Root orchestrates; it never
        # executes commands directly.
        is_root = self.parent is None
        if not getattr(self, "_agent_type_manually_set", False) and not is_root:
            text_lower = text.lower()
            runner_signals = [
                "run command", "execute command", "npm run", "npm install",
                "docker build", "docker run", "pytest", "python -m", "deploy",
                "your task is to run", "execute `npm", "execute the build",
                "run `npm", "run the build", "run the app", "start the server",
                "run the dev", "run the test",
            ]
            assembler_signals = [
                "assemble", "compositor", "integrate all", "single final file",
                "combine all", "merge all", "stitch together", "final assembled",
                "read all team output", "read outputs from", "page compositor",
            ]
            if any(s in text_lower for s in runner_signals):
                self.agent_type = "runner"
            elif any(s in text_lower for s in assembler_signals):
                self.agent_type = "assembler"
            # else: stays "writer"

        # ── Extract namespace ─────────────────────────────────────────────────────
        match = re.search(r'restricted to the `([^`]+)`', text)
        if match:
            return match.group(1).strip()
        return ""

        
    def invoke_agent(self, user_message: str):
        """Invoke the agent with the user message and thread configuration"""
        if not self.agent:
            print(f"❌ Agent not initialized for {self.common_name}")
            return None
            
        config = {"configurable": {"thread_id": self.thread_id}}
        response = self.agent.invoke({"messages": [("user", user_message)]}, config)
        
        # Save conversation history to Redis for persistence across sessions
        # Extract all messages from response
        messages = response.get('messages', [])
        
        # Convert messages to simple dict format for Redis storage
        conversation_history = []
        for msg in messages:
            conversation_history.append({
                "role": msg.type if hasattr(msg, 'type') else "unknown",
                "content": msg.content if hasattr(msg, 'content') else str(msg)
            })
        
        # Trim to last 23 messages (user requested limit)
        conversation_history = conversation_history[-23:]
        
        # Save to Redis under a conversation-specific key
        import json
        
        conversation_key = f"conversation:{self.common_name}"
        redis_client.set(conversation_key, json.dumps(conversation_history))
        
        # Also update context_keyvalue for inspect_neuron display
        self.context_keyvalue = [{"conversation_turn": i+1, "message": msg} for i, msg in enumerate(conversation_history)]
        
        return response

    def add_child(self, child: "AgentNode"):
        child.parent = self
        self.children.append(child)

    def add_skill(self, skill) -> "AgentNode":
        """Attach a Skill to this agent. Returns self for chaining."""
        self.skills.append(skill)
        return self

    def update_dynamic_name(self, new_name: str):
        self.dynamic_name = new_name
        self.save_role_to_redis()

    def save_role_to_redis(self):
        key = f"neuron_role:{self.session_id}:{self.common_name}"
        data = {
            "dynamic_name": self.dynamic_name,
            "system_prompt": self.system_prompt
        }
        redis_client.set(key, json.dumps(data))

    def save_to_redis(self):
        """Persist the full neuron data (including parent relationship) to Redis.
        Uses the 'neuron:' prefix that rebuild_tree_from_redis() expects."""
        key = f"neuron:{self.session_id}:{self.common_name}"
        data = {
            "session_id": self.session_id,
            "common_name": self.common_name,
            "dynamic_name": self.dynamic_name,
            "subtask_provided": self.subtask_provided,
            "original_task": self.original_task,
            "system_prompt": self.system_prompt,
            "activate_flag": self.activate_flag,
            "parent_common_name": self.parent.common_name if self.parent else None,
            "skills": [s.model_dump(exclude={"tools"}) for s in self.skills] if hasattr(self, "skills") else [],
            "execution_stage": self.execution_stage,
            "module_name": self.module_name,
            "agent_type": self.agent_type,
            "_agent_type_manually_set": getattr(self, "_agent_type_manually_set", False),
            "retry_count": getattr(self, 'retry_count', 0),
            "past_failures": getattr(self, 'past_failures', []),
            "model": getattr(self, "model", None) or "moonshot/kimi-k2.5",
            "tools": [t.name for t in self.tools] if (hasattr(self, "tools") and self.tools) else []
        }
        redis_client.set(key, json.dumps(data))

    @staticmethod
    def save_tree_to_redis(root: "AgentNode", session_id: str = "default", clear_first: bool = True):
        """Recursively save the entire tree to Redis."""
        if clear_first:
            # Clear old tree from Redis for this specific session
            for key in redis_client.keys(f"neuron:{session_id}:*"):
                redis_client.delete(key)
            for key in redis_client.keys(f"neuron_role:{session_id}:*"):
                redis_client.delete(key)
                
        root.save_to_redis()
        for child in root.children:
            AgentNode.save_tree_to_redis(child, session_id=session_id, clear_first=False)

    def load_role_from_redis(self):
        """Restore the role (dynamic_name) from Redis if it exists"""
        key = f"neuron_role:{self.session_id}:{self.common_name}"
        data = redis_client.get(key)
        if data:
            try:
                # Try parsing as JSON (new format)
                parsed = json.loads(data.decode("utf-8"))
                if isinstance(parsed, dict):
                    self.dynamic_name = parsed.get("dynamic_name", self.dynamic_name)
                    self.system_prompt = parsed.get("system_prompt", "")
                else:
                    # Fallback for old string format
                    self.dynamic_name = parsed
            except json.JSONDecodeError:
                # Fallback for raw string (old format)
                self.dynamic_name = data.decode("utf-8")
                
            return True
        return False

    def save_context_to_redis(self, user_input: str = None):
        # Store child subtasks as a list of dicts
        child_subtasks = [
            {
                "common_name": child.common_name,
                "dynamic_name": child.dynamic_name,
                "subtask_provided": child.subtask_provided,
                "system_prompt": child.system_prompt
            }
            for child in self.children
        ]

        # Build context entry
        context_entry = {
            "original_task": self.original_task,
            "subtask_provided": self.subtask_provided,
            "child_neurons_subtasks": child_subtasks,
            "system_prompt": self.system_prompt
        }

        if user_input:
            context_entry["user_input"] = user_input

        # Maintain last 5 contexts in memory
        self.context_keyvalue.append(context_entry)
        self.context_keyvalue = self.context_keyvalue[-5:]

        # Save to Redis with duplicate check
        dynamic_key = f"context:{self.dynamic_name}"
        common_key = f"context:{self.common_name}"

        # Get latest from Redis
        last_entry = redis_client.lindex(dynamic_key, 0)
        if not last_entry or json.loads(last_entry.decode("utf-8")) != context_entry:
            # Only push if different
            redis_client.lpush(dynamic_key, json.dumps(context_entry))
            redis_client.ltrim(dynamic_key, 0, 4)  # keep last 5

            redis_client.lpush(common_key, json.dumps(context_entry))
            redis_client.ltrim(common_key, 0, 4)  # keep last 5

    def get_context_from_redis(self):
        dynamic_key = f"context:{self.dynamic_name}"
        context_entries = redis_client.lrange(dynamic_key, 0, 4)  # ✅ last 5
        parsed_entries = [json.loads(entry.decode("utf-8")) for entry in context_entries]
        return parsed_entries

    def get_unique_original_tasks(self):
        """Retrieve unique original tasks (order preserved, reversed) from Redis"""
        # Fetch all contexts for this neuron
        contexts = self.get_context_from_redis()
        
        original_tasks = [ctx.get("original_task") for ctx in contexts if "original_task" in ctx]
        
        # Preserve order and remove duplicates
        unique_tasks = []
        seen = set()
        for task in original_tasks:
            if task not in seen:
                seen.add(task)
                unique_tasks.append(task)
        
        # Reverse order
        unique_tasks.reverse()
        
        # Convert to list of dictionaries
        return [{f"conversation-{i+1}": task} for i, task in enumerate(unique_tasks)]

    def find_neuron_by_name(self, name):
        """Find a neuron by common_name or dynamic_name"""
        if self.common_name == name or self.dynamic_name == name:
            return self
        
        for child in self.children:
            found = child.find_neuron_by_name(name)
            if found:
                return found
        
        return None
