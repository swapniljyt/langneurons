from rich.tree import Tree
from rich.text import Text
from rich.panel import Panel
from rich.console import Console
from rich.live import Live
import asyncio

class Visualizer:
    def __init__(self):
        self.console = Console()

    async def stream_task_assignment(self, neuron_name, role, task, duration=0.005):
        """
        Simulates token-by-token streaming of the task assignment.
        Async non-blocking version using asyncio.sleep.
        """
        header = Text(f"🧠 Assigning to {neuron_name} ({role})...\n", style="bold green")
        
        # Initial empty panel
        content = Text("")
        panel = Panel(
            content,
            title=header,
            border_style="green",
            padding=(1, 2),
            expand=False
        )
        
        # We process in chunks to speed up the visual effect without losing the "feel"
        chunk_size = 3 
        
        with Live(panel, console=self.console, refresh_per_second=30) as live:
            # Stream the task text
            for i in range(0, len(task) + 1, chunk_size):
                content = Text(task[:i+chunk_size], style="green")
                panel = Panel(
                    content,
                    title=header,
                    border_style="green",
                    padding=(1, 2),
                    expand=False
                )
                live.update(panel)
                await asyncio.sleep(duration)



    def get_status_emoji(self, neuron):
        """Get emoji based on activation status"""
        return "🔥" if neuron.activate_flag else "💤"

    def format_task_text(self, task_text, max_length=25):
        """Format task text with dotted progress if it exceeds max_length words"""
        if not task_text:
            return task_text
        
        words = task_text.split()
        
        if len(words) <= max_length:
            return task_text
        else:
            # Take first few words and add dotted progress
            truncated_words = words[:max_length]
            truncated_text = " ".join(truncated_words)
            
            # Calculate dots needed (aim for around 60-80 total characters)
            current_length = len(truncated_text)
            target_length = min(80, current_length + 20)  # Don't make it too long
            dots_needed = max(3, target_length - current_length)
            
            return f"{truncated_text}{'.' * dots_needed}"

    def format_system_prompt(self, system_prompt, max_length=50):
        """Format system prompt with truncation for display"""
        if not system_prompt:
            return "❌ No System Prompt"
        
        # Remove extra whitespace and newlines
        cleaned_prompt = ' '.join(system_prompt.split())
        
        if len(cleaned_prompt) <= max_length:
            return f"✅ {cleaned_prompt}"
        else:
            # Truncate and add ellipsis
            truncated = cleaned_prompt[:max_length].rstrip()
            return f"✅ {truncated}..."

    def get_color_by_level(self, level, is_active):
        """Enhanced color scheme with better contrast"""
        if is_active:
            # Vibrant colors for active neurons
            active_colors = [
                "bold bright_cyan",      # Level 0 - Bright cyan
                "bold bright_green",     # Level 1 - Bright green  
                "bold bright_yellow",    # Level 2 - Bright yellow
                "bold bright_magenta",   # Level 3 - Bright magenta
                "bold bright_red",       # Level 4 - Bright red
                "bold bright_blue"       # Level 5 - Bright blue
            ]
            return active_colors[level % len(active_colors)]
        else:
            # Muted colors for inactive neurons
            return "dim italic #666666"

    def render_tree(self, neuron, level=0, show_system_prompt=True) -> Tree:
        # Get status emoji only
        status_emoji = self.get_status_emoji(neuron)
        
        # Choose style based on activation flag
        style = self.get_color_by_level(level, neuron.activate_flag)
        
        # Format only main task with dotted progress if needed
        formatted_main_task = self.format_task_text(neuron.original_task)
        # Keep subtask as-is without formatting
        formatted_subtask = neuron.subtask_provided
        
        # Format system prompt
        formatted_system_prompt = self.format_system_prompt(neuron.system_prompt)
        
        # Get assigned tools using the registry
        from core.tools.registry import get_tool_names_for_agent
        assigned_tools = get_tool_names_for_agent(neuron.agent_type)
        tools_str = ", ".join(assigned_tools) if assigned_tools else "None"
        
        # Create clean node text with system prompt and tools
        base_info = (
            f"{status_emoji} [Level {level}] - {'ACTIVE' if neuron.activate_flag else 'INACTIVE'}\n"
            f"Common Name : {neuron.common_name}\n"
            f"Dynamic Name: {neuron.dynamic_name}\n"
            f"Agent Type  : {neuron.agent_type}\n"
            f"Tools       : {tools_str}\n"
            f"Main Task   : {formatted_main_task}\n"
            f"Subtask     : {formatted_subtask}"
        )
        
        # Add system prompt if requested
        if show_system_prompt:
            base_info += f"\nSystem Prompt: {formatted_system_prompt}"
        
        node_text = Text(base_info, style=style)
        tree = Tree(node_text)
        
        # Add children
        for child in neuron.children:
            tree.add(self.render_tree(child, level + 1, show_system_prompt))
        
        return tree

    def render_beautiful_tree(self, neuron, title="🧠 Neural Network Tree", show_system_prompt=True):
        """Render the tree with a beautiful panel wrapper"""
        tree = self.render_tree(neuron, show_system_prompt=show_system_prompt)
        
        # Wrap in a beautiful panel
        panel = Panel(
            tree,
            title=f"[bold bright_cyan]{title}[/]",
            border_style="bright_blue",
            padding=(1, 2),
            expand=False
        )
        
        self.console.print(panel)
        return panel

    def get_tree_stats(self, neuron):
        """Get statistics about the neuron tree including system prompt info"""
        def count_neurons(node):
            active_count = 1 if node.activate_flag else 0
            inactive_count = 0 if node.activate_flag else 1
            total_count = 1
            has_prompt_count = 1 if node.system_prompt else 0
            
            for child in node.children:
                child_active, child_inactive, child_total, child_prompts = count_neurons(child)
                active_count += child_active
                inactive_count += child_inactive
                total_count += child_total
                has_prompt_count += child_prompts
                
            return active_count, inactive_count, total_count, has_prompt_count
        
        active, inactive, total, with_prompts = count_neurons(neuron)
        return {
            "total_neurons": total,
            "active_neurons": active,
            "inactive_neurons": inactive,
            "neurons_with_prompts": with_prompts,
            "activation_rate": f"{(active/total)*100:.1f}%" if total > 0 else "0%",
            "prompt_coverage": f"{(with_prompts/total)*100:.1f}%" if total > 0 else "0%"
        }

    def print_tree_with_stats(self, neuron, title="🧠 Neural Network Analysis", show_system_prompt=True):
        """Print tree with statistics including system prompt stats"""
        # Get statistics
        stats = self.get_tree_stats(neuron)
        
        # Create enhanced stats text
        stats_text = Text(
            f"📊 Total Neurons: {stats['total_neurons']} | "
            f"🔥 Active: {stats['active_neurons']} | "
            f"💤 Inactive: {stats['inactive_neurons']} | "
            f"⚡ Activation Rate: {stats['activation_rate']} | "
            f"🤖 With Prompts: {stats['neurons_with_prompts']} | "
            f"📝 Prompt Coverage: {stats['prompt_coverage']}",
            style="bold bright_white"
        )
        
        # Render tree with system prompts
        tree = self.render_tree(neuron, show_system_prompt=show_system_prompt)
        
        # Create main panel with stats
        from rich.console import Group
        
        main_panel = Panel(
            Group(stats_text, Text("\n"), tree),
            title=f"[bold bright_cyan]{title}[/]",
            border_style="bright_blue",
            padding=(1, 2),
            expand=False
        )
        
        self.console.print(main_panel)
        return main_panel

    def print_system_prompts_only(self, neuron, title="🤖 System Prompts Overview"):
        """Print a focused view of just the system prompts for all neurons"""
        
        def collect_prompts(node, level=0):
            prompts_info = []
            indent = "  " * level
            
            if node.system_prompt:
                # Truncate long prompts for overview
                prompt_preview = node.system_prompt[:100].replace('\n', ' ') + "..." if len(node.system_prompt) > 100 else node.system_prompt.replace('\n', ' ')
                status = "🔥 ACTIVE" if node.activate_flag else "💤 INACTIVE"
                
                prompts_info.append(
                    f"{indent}• {status} {node.common_name} ({node.dynamic_name})\n"
                    f"{indent}  📝 {prompt_preview}"
                )
            else:
                status = "🔥 ACTIVE" if node.activate_flag else "💤 INACTIVE"
                prompts_info.append(
                    f"{indent}• {status} {node.common_name} ({node.dynamic_name})\n"
                    f"{indent}  ❌ No System Prompt Set"
                )
            
            for child in node.children:
                prompts_info.extend(collect_prompts(child, level + 1))
            
            return prompts_info
        
        all_prompts = collect_prompts(neuron)
        prompts_text = "\n\n".join(all_prompts)
        
        # Create panel
        panel = Panel(
            prompts_text,
            title=f"[bold bright_cyan]{title}[/]",
            border_style="bright_magenta",
            padding=(1, 2),
            expand=False
        )
        
        self.console.print(panel)
        return panel

    def print_detailed_system_prompt(self, neuron, neuron_name=None):
        """Print detailed system prompt for a specific neuron or current neuron"""
        
        if neuron_name:
            # Find the specific neuron
            target_neuron = neuron.find_neuron_by_name(neuron_name)
            if not target_neuron:
                self.console.print(f"❌ Neuron '{neuron_name}' not found")
                return
        else:
            target_neuron = neuron
        
        # Create detailed prompt display
        status = "🔥 ACTIVE" if target_neuron.activate_flag else "💤 INACTIVE"
        
        prompt_content = target_neuron.system_prompt if target_neuron.system_prompt else "❌ No System Prompt Set"
        
        detailed_info = (
            f"Neuron: {target_neuron.common_name} ({target_neuron.dynamic_name})\n"
            f"Status: {status}\n"
            f"Original Task: {target_neuron.original_task}\n"
            f"Subtask: {target_neuron.subtask_provided}\n\n"
            f"System Prompt:\n{prompt_content}"
        )
        
        panel = Panel(
            detailed_info,
            title=f"[bold bright_green]🤖 System Prompt Details[/]",
            border_style="bright_green",
            padding=(1, 2),
            expand=False
        )
        
        self.console.print(panel)
        return panel
