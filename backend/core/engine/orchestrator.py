"""
core/engine/orchestrator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER  : Engine
ROLE   : The Swarm Scheduler — walks the AgentNode tree depth-first and dispatches agents.

KEY CONCEPTS IN THIS FILE:
  • Orchestrator class        (line ~15)  — Central controller instantiated by swarm.py
  • _build_phase()            (line ~80)  — Unfreeze path: skill-gen + task decomposition
  • _freeze_phase()           (line ~180) — Freeze path: loads tree → runs chat loop
  • _dispatch_level()         (line ~250) — Runs all agents at the same tree depth in parallel
  • ActivationRouter          (imported)  — Decides which agents are active vs dormant
  • TaskDecomposer            (imported)  — Breaks FORMATION_BRIEF into per-agent subtasks
  • SkillGenerator            (imported)  — Generates the system-prompt .md file per agent

DEPENDS ON:
  • core/engine/llm_gateway.py      — structured LLM calls (router tier)
  • core/modules/skill_generator.py — auto-generates agent skills from FORMATION_BRIEF
  • core/agents/agent_node.py       — the AgentNode tree data model
  • core/agents/visualizer.py       — pretty-prints the tree to console

CALLED BY:
  • core/swarm.py → run_swarm()
"""

import os
import asyncio
from typing import List, Dict, TypeVar
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor

from ..engine.llm_gateway import StructuredChatClient
from ..modules.activation_router import ActivationRouter
from ..modules.role_manager import RoleManager
from ..modules.task_decomposer import TaskDecomposer
from ..modules.skill_generator import SkillGenerator
from ..agents.agent_node import AgentNode
from ..agents.visualizer import Visualizer

class Orchestrator:
    """
    The Central Controller (Orchestrator).
    Orchestrates the Modules and Agents to execute tasks.
    """
    def __init__(self, freeze_mode: bool = False):
        # Freeze/Unfreeze Mode
        # freeze_mode=False (unfreeze) → orchestration building mode, always rebuild tree (non-contextual)
        # freeze_mode=True  (freeze)   → locked tree mode, reuse existing roles (contextual)
        self.freeze_mode = freeze_mode

        # Initialize Thalamus (LLM Gateway)
        self.llm_client = StructuredChatClient()

        # Initialize Modules
        self.activation_router = ActivationRouter(self.llm_client)
        self.role_manager = RoleManager(self.llm_client)
        self.task_decomposer = TaskDecomposer(self.llm_client)
        self.skill_generator = SkillGenerator(self.llm_client)
        
        # Initialize Visualizer (Output)
        self.visualizer = Visualizer()
        self.console = self.visualizer.console
        
        # State
        self.delegator_task_split_level_map = None
        self.root = None
        
        # Concurrency Control (Optimize based on CPU)
        # Using cpu_count * 2 for I/O bound tasks to maximize throughput while respecting device limits
        cpu_count = os.cpu_count() or 1
        self.max_concurrency = cpu_count * 2
        self.semaphore = asyncio.Semaphore(self.max_concurrency)
        self.console.print(f"[dim]⚙️  Optimized parallelism: {self.max_concurrency} concurrent streams (CPU: {cpu_count})[/dim]")

    def generate_neural_schema(self) -> str:
        """
        Generates a text-based schema of the current neural architecture.
        Used to give the ReticularFormation global context.
        """
        if not self.root:
            return "No neural architecture initialized."

        lines = []
        
        def traverse(neuron, prefix="", is_last=True):
            # Define symbols
            connector = "└── " if is_last else "├── "
            child_prefix = "    " if is_last else "│   "
            
            # Add current neuron line
            role = neuron.dynamic_name if hasattr(neuron, 'dynamic_name') else "Unassigned"
            lines.append(f"{prefix}{connector}{neuron.common_name} ({role})")
            
            # Process children
            children_count = len(neuron.children)
            for i, child in enumerate(neuron.children):
                is_last_child = (i == children_count - 1)
                traverse(child, prefix + child_prefix, is_last_child)

        # Start traversal from root (handled slightly differently as having no connector)
        lines.append(f"{self.root.common_name} ({self.root.dynamic_name})")
        for i, child in enumerate(self.root.children):
            is_last_child = (i == len(self.root.children) - 1)
            traverse(child, "", is_last_child)
            
        return "\n".join(lines)

    async def assign_system_prompts(self, neurons: List[AgentNode], original_task: str):
        """Assign or update system prompts for multiple neurons"""
        
        # Build complete team directory from ALL neurons in the entire tree
        def collect_all_neurons(node, collection):
            """Recursively collect all activated neurons from the tree"""
            if node.activate_flag and node.dynamic_name:
                collection.append({"name": node.common_name, "role": node.dynamic_name})
            for child in node.children:
                collect_all_neurons(child, collection)
        
        all_neurons_list = []
        if self.root:
            collect_all_neurons(self.root, all_neurons_list)
        
        team_directory = all_neurons_list
        
        tasks = []
        for neuron in neurons:
            if neuron.activate_flag and neuron.subtask_provided and not neuron.system_prompt:
                custom_persona = getattr(neuron, 'custom_persona', None) if getattr(neuron, 'is_custom_prompt', False) else None

                # Extract hierarchical context
                parent_info = None
                if neuron.parent:
                    parent_info = {
                        "name": neuron.parent.common_name,
                        "role": neuron.parent.dynamic_name
                    }
                
                # Extract children
                children_info = [
                    {"name": child.common_name, "role": child.dynamic_name}
                    for child in neuron.children
                ]
                
                # No longer extracting siblings - pure hierarchical structure
                
                tasks.append(
                    self.role_manager.assign_system_prompt(
                        common_name=neuron.common_name,
                        role=neuron.dynamic_name,
                        original_task=original_task,
                        First_subtask_task=neuron.subtask_provided,
                        parent_info=parent_info,
                        children_info=children_info,
                        siblings_info=None,  # No longer used
                        team_directory=team_directory,
                        custom_persona=custom_persona,
                        agent_type=neuron.agent_type
                    )
                )
        
        status_msg = (
            "[bold green]🧠 Assigning system prompts to neurons...[/bold green]\n"
            "[dim]ℹ️  Sending concurrent requests to the LLM API. "
            "This may take a moment depending on your API speed...[/dim]"
        )
        with self.console.status(status_msg, spinner="dots"):
            results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                self.console.print(f"[red]⚠️ Role manager prompt assignment failed: {result}[/red]")
                continue
            if result is None:
                continue
            for neuron in neurons:
                if neuron.common_name == result.common_name:
                    # Verify assignment before setting
                    prompt_preview = result.system_prompt[:100] + "..." if len(result.system_prompt) > 100 else result.system_prompt
                    self.console.print(f"[dim]🔍 Assigning prompt to {neuron.common_name}: {prompt_preview}[/dim]")
                    
                    neuron.system_prompt = result.system_prompt
                    
                    # Verify the assignment succeeded
                    if neuron.system_prompt:
                        self.console.print(f"📝 Updated system prompt for [green]{neuron.common_name}[/green] (length: {len(neuron.system_prompt)} chars)")
                    else:
                        self.console.print(f"[red]⚠️ WARNING: system_prompt is empty for {neuron.common_name}![/red]")
                    
                    # Save intermediate prompt to Redis for real-time console updates
                    neuron.save_to_redis()
                    
        # ── AUTO-GENERATE SKILLS IF MISSING (fallback only) ──────────────────────
        # Only runs if role_manager above did NOT produce a system_prompt.
        # Prevents overwriting already-assigned, high-quality prompts with the
        # smaller SkillPromptResponse output.
        skill_tasks = []
        neurons_needing_skills = []
        for neuron in neurons:
            if neuron.activate_flag and not neuron.system_prompt:
                skill_tasks.append(
                    self.skill_generator.generate_system_prompt(
                        agent_node=neuron,
                        root_node=self.root or neuron,
                        original_task=original_task,
                        subtask_provided=neuron.subtask_provided or neuron.dynamic_name or neuron.common_name,
                        session_id=getattr(neuron, 'session_id', 'default'),
                        user_instruction=neuron.behavior_hint,
                    )
                )
                neurons_needing_skills.append(neuron)
                
        if skill_tasks:
            # Moonshot rate limit: max 3 concurrent requests. Use semaphore of 2 to be safe.
            skill_sem = asyncio.Semaphore(2)

            async def _bounded_skill(task):
                async with skill_sem:
                    return await task

            bounded = [_bounded_skill(t) for t in skill_tasks]
            status_msg = (
                "[bold green]⚡ Auto-generating skill prompts for fallback neurons...[/bold green]\n"
                "[dim]ℹ️  Generating agent personas and skills via parallel LLM API requests. "
                "This step is computationally intensive and subject to provider rate limits. Please stand by...[/dim]"
            )
            with self.console.status(status_msg, spinner="dots"):
                skill_results = await asyncio.gather(*bounded, return_exceptions=True)
            for res, neuron in zip(skill_results, neurons_needing_skills):
                if isinstance(res, Exception):
                    self.console.print(f"[red]⚠️ Skill generation failed for {neuron.common_name}: {res}[/red]")
                    continue
                result_prompt, agent_type = res
                # generate_system_prompt returns (prompt_str, agent_type) tuple
                self.console.print(f"[dim]⚡ Auto-generated skill prompt for {neuron.common_name} ({len(result_prompt)} chars) | type={agent_type}[/dim]")
                neuron.system_prompt = result_prompt    # ← always a str, never the raw tuple
                neuron.agent_type = agent_type
                neuron.save_to_redis()


    async def refresh_all_team_directories(self, original_task: str):
        """
        After tree construction is complete, directly PATCH the TEAM DIRECTORY and COMMAND
        HIERARCHY sections in every neuron's system prompt — no LLM call needed. This avoids
        the LLM reformatting the tree into a flat bullet list.
        """
        self.console.print("\n[bold cyan]🔄 Updating all team directories with complete team...[/bold cyan]")

        _SEP = "━" * 20

        # ── 1. Build the hierarchical tree string ──────────────────────────────
        def generate_tree_string(node, prefix="", is_last=True, is_root=True):
            if not node.activate_flag or not node.dynamic_name:
                return ""
            if is_root:
                line = f"{node.common_name} — {node.dynamic_name}\n"
                new_prefix = ""
            else:
                connector = "└── " if is_last else "├── "
                line = f"{prefix}{connector}{node.common_name} — {node.dynamic_name}\n"
                new_prefix = prefix + ("    " if is_last else "│   ")
            active_children = [c for c in node.children if c.activate_flag and c.dynamic_name]
            for i, child in enumerate(active_children):
                line += generate_tree_string(child, new_prefix, i == len(active_children) - 1, is_root=False)
            return line

        team_tree = generate_tree_string(self.root).rstrip() if self.root else "(No team information available)"
        total_neurons = team_tree.count("\n") + 1
        self.console.print(f"[dim]📊 Generated team hierarchy with {total_neurons} neurons[/dim]")

        # ── 2. Build a replacement TEAM DIRECTORY block ────────────────────────
        team_dir_block = (
            f"{_SEP}\nTEAM DIRECTORY\n{_SEP}\n"
            f"You are part of the following agent team (hierarchical view):\n\n"
            f"{team_tree}\n\n"
            f"This directory shows the command structure and your position within the team."
        )

        # ── 3. Collect all neurons that already have a system prompt ───────────
        neurons_to_update = []
        def collect(node, col):
            if node.activate_flag and node.system_prompt:
                col.append(node)
            for child in node.children:
                collect(child, col)
        if self.root:
            collect(self.root, neurons_to_update)

        # ── 4. For each neuron, surgically patch the two sections ──────────────
        updated = 0
        for neuron in neurons_to_update:
            prompt = neuron.system_prompt

            # ── patch TEAM DIRECTORY ───────────────────────────────────────────
            td_start_marker = f"{_SEP}\nTEAM DIRECTORY\n{_SEP}"
            # The section ends just before the next ━━━ separator
            td_start = prompt.find(td_start_marker)
            if td_start != -1:
                # Find where the NEXT separator block begins (COMMAND HIERARCHY)
                next_sep = prompt.find(_SEP, td_start + len(td_start_marker))
                if next_sep != -1:
                    # Walk back to include the newlines before the separator
                    # We want to replace everything from td_start to next_sep (non-inclusive)
                    prompt = prompt[:td_start] + team_dir_block + "\n\n" + prompt[next_sep:]

            # ── patch COMMAND HIERARCHY ────────────────────────────────────────
            ch_marker = f"{_SEP}\nCOMMAND HIERARCHY\n{_SEP}"
            ch_start = prompt.find(ch_marker)
            if ch_start != -1:
                # Build correct boss / subordinates lines
                if neuron.parent:
                    boss = (
                        f"- {neuron.parent.common_name} ({neuron.parent.dynamic_name})\n"
                        f"You must follow instructions from your boss and align your work accordingly."
                    )
                else:
                    boss = "- None (You are a top-level coordinator)"

                children = [c for c in neuron.children if c.activate_flag and c.dynamic_name]
                if children:
                    sub_lines = "\n".join(f"- {c.common_name} — {c.dynamic_name}" for c in children)
                    subordinates = sub_lines + "\nDelegate tasks and integrate their outputs."
                else:
                    subordinates = "- None (No junior agents under you)"

                ch_block = (
                    f"{_SEP}\nCOMMAND HIERARCHY\n{_SEP}\n\n"
                    f"Boss (Supervisor):\n{boss}\n\n"
                    f"Subordinates (Junior Agents):\n{subordinates}"
                )

                # Find RESPONSIBILITIES section as the end boundary
                resp_marker = f"{_SEP}\nRESPONSIBILITIES\n{_SEP}"
                resp_start = prompt.find(resp_marker, ch_start)
                if resp_start != -1:
                    prompt = prompt[:ch_start] + ch_block + "\n\n" + prompt[resp_start:]
                else:
                    # If no RESPONSIBILITIES section, just replace to end
                    prompt = prompt[:ch_start] + ch_block

            neuron._system_prompt = prompt  # bypass setter to avoid is_custom_prompt interference
            neuron.save_role_to_redis()
            neuron.initialize_agent()
            updated += 1

        self.console.print(f"[bold green]✅ Updated {updated} neurons with complete team directory[/bold green]\n")


    def propagate_original_task(self, root, original_task):
        queue = deque([root])
        while queue:
            neuron = queue.popleft()
            neuron.original_task = original_task
            for child in neuron.children:
                queue.append(child)

    def initialize_all_neurons(self, root):
        queue = deque([root])
        while queue:
            neuron = queue.popleft()
            neuron.activate_flag = False
            # Restore persistent role from Redis (Brain Plasticity/Memory)
            if neuron.load_role_from_redis():
                self.console.print(f"[dim]🧠 Restored role for {neuron.common_name}: {neuron.dynamic_name}[/dim]")
                # Initialize agent for restored role
                neuron.initialize_agent()

            if hasattr(neuron, 'subtask_provided') and neuron.subtask_provided is None:
                neuron.subtask_provided = "Placeholder Subtask"
            for child in neuron.children:
                queue.append(child)

    def build_level_map(self, root):
        level_map = defaultdict(list)
        queue = deque([(root, 0)])
        while queue:
            neuron, level = queue.popleft()
            level_map[level].append(neuron)
            for child in neuron.children:
                queue.append((child, level + 1))
        return level_map

    def is_leaf_node(self, neuron):
        return len(neuron.children) == 0

    async def process_single_parent(self, parent, original_task):
        """Process single parent neuron and its children"""
        try:
            if self.is_leaf_node(parent):
                self.console.print(f"🍃 [yellow]{parent.common_name}[/yellow] is leaf node")
                return

            self.console.print(f"🧩 Processing parent: [cyan]{parent.common_name}[/cyan]")
            
            neuron_roles = {
                child.common_name: {
                    "role": child.dynamic_name,
                    "system_prompt": child.system_prompt
                }
                for child in parent.children
            }
            context = parent.get_context_from_redis()
            realtime_subtask = parent.subtask_provided           
            
            # Garbarge prints removed
            # print(f"1.neuron roles:=====>>> {neuron_roles}")
            # print(f"2.realtime subtask:=====>>> {realtime_subtask}") 
            
            # Generate schema for context
            neural_schema = self.generate_neural_schema()

            # Activation (Activation Router)
            activation = await self.activation_router.activate_neurons(
                neuron_roles, 
                self.freeze_mode, 
                realtime_subtask, 
                original_task,
                neural_schema # Pass the full map
            )
            # print(f"activation.Fired_Neurons:=====> {activation.Fired_Neurons}") # REMOVED GARBAGE PRINT
            activated_neuron_names = {n.common_name: n.dynamic_name for n in activation.Fired_Neurons}

            # Decomposition (Task Decomposer)
            if activation.context_flag:
                result = await self.task_decomposer.async_contextual_decompose_task(
                    original_task=original_task,
                    parent_task=realtime_subtask,
                    neurons_dict=activated_neuron_names,
                    context=context,
                    parent_role=parent.dynamic_name
                )
                self.console.print("✅ Using contextual decomposition")
            else:
                self.console.print("🔄 No context match - creating new assignments")
                result = await self.task_decomposer.async_non_contextual_decompose_task(
                    original_task=original_task,
                    parent_task=realtime_subtask,
                    neurons_dict=activated_neuron_names,
                    parent_role=parent.dynamic_name
                )

            # Reset children activation states
            for child in parent.children:
                child.activate_flag = False

            # Activate fired children and assign subtasks
            valid_fired_names = set(n.common_name for n in activation.Fired_Neurons)
            for i, child in enumerate(parent.children):
                if child.common_name in valid_fired_names:
                    child.activate_flag = True
                    # Find matching subtask from result
                    # Note: We assume order matches or we need to match by name if provided in result
                    # The decomposition result has list of SubTask_by_name
                    # Let's find the specific subtask for this child
                    found_subtask = next((s for s in result.subtasks if s.common_name == child.common_name), None)
                    
                    if found_subtask:
                        child.subtask_provided = found_subtask.subtask
                        if hasattr(found_subtask, 'responsibility_domain'):
                            child.responsibility_domain = found_subtask.responsibility_domain
                        if not getattr(child, 'is_custom_prompt', False):
                            child.update_dynamic_name(found_subtask.dynamic_name)
                        # Store build_stage for sequential stage execution
                        child.execution_stage = getattr(found_subtask, 'build_stage', 0)
                        # Store agent_type for namespace enforcement (domain-agnostic)
                        # Only override if not manually set (manual set wins over LLM inference)
                        llm_agent_type = getattr(found_subtask, 'agent_type', None)
                        if llm_agent_type in ("writer", "runner", "assembler"):
                            if not getattr(child, '_agent_type_manually_set', False):
                                child.agent_type = llm_agent_type

                    
                    # self.console.print(f"✅ Activated: {child.common_name}")
                    # Use Visualizer Streaming Effect (Async)
                    await self.visualizer.stream_task_assignment(
                        child.common_name,
                        child.dynamic_name,
                        child.subtask_provided
                    )
                else:
                    # Keep deactivation simple/dimmed
                    self.console.print(f"[dim]💤 Deactivated: {child.common_name}[/dim]")

            # Assign prompts (Temporal Lobe) AFTER activation + subtasks
            if not activation.context_flag:
                await self.assign_system_prompts(parent.children, original_task)

            parent.save_context_to_redis()
            
        except Exception as e:
            self.console.print(f"❌ Error processing {parent.common_name}: {str(e)}")
            raise e

    async def start_reaction(self, original_task: str, root, depth: int = None, current_depth: int = 0):
        """
        Main entry point for the Brain's reaction loop (formerly delegator_task_split).
        """
        session_id = getattr(root, 'session_id', 'default')
        if current_depth == 0:
            self.root = root  # Store root for schema generation
            
            # Clear old skills to force regeneration for this session (only if building)
            if not self.freeze_mode:
                self.skill_generator.clear_session_skills(session_id)
            
            self.initialize_all_neurons(root)
            self.propagate_original_task(root, original_task)
            self.delegator_task_split_level_map = self.build_level_map(root)

        if depth is None:
            depth = max(self.delegator_task_split_level_map.keys())

        if current_depth > depth:
            # Pipeline complete - update all prompts with complete team directory
            await self.refresh_all_team_directories(original_task)
            return

        self.console.rule(f"[bold cyan]🔁 Depth {current_depth}")

        if current_depth == 0:
            # Root level processing
            root.activate_flag = True
            root.subtask_provided = original_task
            root.update_dynamic_name("task_coordinator")

            # Generate system prompt and skill for root if it lacks either
            if not root.system_prompt or not root.skills:
                await self.assign_system_prompts([root], original_task)

            if root.children:
                neuron_roles = {
                    child.common_name: {
                        "role": child.dynamic_name,
                        "system_prompt": child.system_prompt
                    }
                    for child in root.children
                }
                context = root.get_unique_original_tasks()
                realtime_subtask = root.subtask_provided
                
                # Garbage prints removed
                # print(f"1.neuron roles:=====>>> {neuron_roles}")
                # print(f"2.realtime subtask:=====>>> {realtime_subtask}")   
                
                # Generate schema for context
                neural_schema = self.generate_neural_schema()
                
                status_msg = (
                    "[bold green]🔌 Determining neuron activations & decomposing root task...[/bold green]\n"
                    "[dim]ℹ️  Analyzing task structure and routing assignments via LLM. Please stand by...[/dim]"
                )
                with self.console.status(status_msg, spinner="dots"):
                    activation = await self.activation_router.activate_neurons(
                        neuron_roles,
                        self.freeze_mode,
                        realtime_subtask,
                        original_task,
                        neural_schema
                    )
                    # print(f"activation.Fired_Neurons:=====> {activation.Fired_Neurons}")
                    
                    activated_neuron_dict = {n.common_name: n.dynamic_name for n in activation.Fired_Neurons}
                    
                    if activation.context_flag:
                        root_split = await self.task_decomposer.async_contextual_decompose_task(
                            original_task=realtime_subtask,
                            parent_task=realtime_subtask,
                            neurons_dict=activated_neuron_dict,
                            context=context,
                            parent_role="task_coordinator"
                        )
                    else:
                        root_split = await self.task_decomposer.async_non_contextual_decompose_task(
                            original_task=realtime_subtask,
                            parent_task=realtime_subtask,
                            neurons_dict=activated_neuron_dict,
                            parent_role="task_coordinator"
                        )

                # Reset children activation
                for child in root.children:
                    child.activate_flag = False

                # Activate fired neurons
                for child in root.children:
                    if child.common_name in activated_neuron_dict:
                        child.activate_flag = True
                        found_subtask = next((s for s in root_split.subtasks if s.common_name == child.common_name), None)
                        if found_subtask:
                            child.subtask_provided = found_subtask.subtask
                            if not getattr(child, 'is_custom_prompt', False):
                                child.update_dynamic_name(found_subtask.dynamic_name)
                            # Write build_stage so the execution engine can group by stage
                            child.execution_stage = getattr(found_subtask, 'build_stage', 0)

                # Assign prompts
                if not activation.context_flag:
                    await self.assign_system_prompts(root.children, original_task)

                root.save_context_to_redis()
                from core.agents.agent_node import AgentNode
                AgentNode.save_tree_to_redis(root, session_id=session_id, clear_first=False)

        else:
            # PARALLEL PROCESSING for depth > 0
            previous_depth = current_depth - 1
            active_parents = [
                neuron for neuron in self.delegator_task_split_level_map[previous_depth]
                if neuron.activate_flag
            ]
            
            self.console.print(f"Active parents: {[n.common_name for n in active_parents]}")
            
            if active_parents:
                async def sem_task(parent, task):
                    async with self.semaphore:
                        return await self.process_single_parent(parent, task)

                parent_tasks = [
                    sem_task(parent, original_task)
                    for parent in active_parents
                ]
                
                self.console.print(f"🚀 Processing {len(parent_tasks)} parents in parallel (max {self.max_concurrency})...")
                start_time = asyncio.get_event_loop().time()
                
                status_msg = (
                    f"[bold green]🚀 Processing {len(parent_tasks)} parents in parallel...[/bold green]\n"
                    "[dim]ℹ️  Decomposing subtasks and routing activations via concurrent LLM requests. "
                    "This may take a few seconds...[/dim]"
                )
                with self.console.status(status_msg, spinner="dots"):
                    results = await asyncio.gather(*parent_tasks, return_exceptions=True)
                
                end_time = asyncio.get_event_loop().time()
                self.console.print(f"✅ Parallel processing completed in {end_time - start_time:.2f}s")
                
                exceptions = [r for r in results if isinstance(r, Exception)]
                if exceptions:
                    self.console.print(f"⚠️ {len(exceptions)} errors occurred:")
                    for i, exc in enumerate(exceptions):
                        self.console.print(f"  Error {i+1}: {str(exc)}")
                
                from core.agents.agent_node import AgentNode
                AgentNode.save_tree_to_redis(root, session_id=session_id, clear_first=False)

            # Visual feedback
            active_neurons_at_depth = []
            for parent in active_parents:
                for child in parent.children:
                    if child in self.delegator_task_split_level_map[current_depth] and child.activate_flag:
                        active_neurons_at_depth.append(child)
            
            self.console.print(f"Active neurons: {[n.common_name for n in active_neurons_at_depth]}")

            for neuron in active_neurons_at_depth:
                self.console.print(f"🧠 [bold]{neuron.common_name}[/bold] ({neuron.dynamic_name}) → {neuron.subtask_provided[:50]}...")

        # Recursive call
        await self.start_reaction(original_task, root, depth, current_depth + 1)
