"""
core/langtrace/dashboard.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Visual dashboard layouts and real-time Live UI renderer for LangTrace.
"""

import time
import json
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.box import ROUNDED

from core.engine.memory import RedisClient

_redis_instance = RedisClient()
_redis = _redis_instance.get_client()


def find_most_recent_session() -> str:
    """Helper to locate the most recent active session ID from Redis."""
    keys = _redis.keys("execution_history:*")
    if not keys:
        return "default"
    sessions = []
    for k in keys:
        parts = k.decode("utf-8").split(":")
        if len(parts) >= 2:
            sessions.append(parts[1])
    return sessions[-1] if sessions else "default"


def load_records(session_id: str) -> list[dict]:
    """Load all traced LLM records for a session from Redis."""
    key = f"langtrace:{session_id}:calls"
    raw_list = _redis.lrange(key, 0, -1)
    records = []
    for item in raw_list:
        try:
            records.append(json.loads(item.decode("utf-8")))
        except Exception:
            pass
    return records


def build_dashboard(session_id: str) -> Layout:
    """Assembles a Rich dynamic Dashboard Layout for the trace session."""
    records = load_records(session_id)
    
    total_cost = sum(r["cost"] for r in records)
    total_input = sum(r["input_tokens"] for r in records)
    total_output = sum(r["output_tokens"] for r in records)
    total_calls = len(records)

    # 1. Header Pane
    header_text = Text("\n⚡ LANGTRACE™ — Real-Time Swarm Cost & Token Analyzer", style="bold cyan")
    header_text.append(f"\n[Session ID: {session_id}]", style="dim white")
    header = Panel(header_text, style="cyan", border_style="cyan", box=ROUNDED)

    # 2. Grand Metrics Pane
    metrics_table = Table.grid(expand=True)
    metrics_table.add_column(justify="center", ratio=1)
    metrics_table.add_column(justify="center", ratio=1)
    metrics_table.add_column(justify="center", ratio=1)
    metrics_table.add_column(justify="center", ratio=1)
    
    metrics_table.add_row(
        Panel(f"[bold green]${total_cost:.5f}[/bold green]\nTotal Spent (USD)", border_style="green", box=ROUNDED),
        Panel(f"[bold white]{total_calls}[/bold white]\nLLM Invocations", border_style="white", box=ROUNDED),
        Panel(f"[bold yellow]{total_input:,}[/bold yellow]\nInput Tokens", border_style="yellow", box=ROUNDED),
        Panel(f"[bold magenta]{total_output:,}[/bold magenta]\nOutput Tokens", border_style="magenta", box=ROUNDED),
    )
    metrics_pane = Panel(metrics_table, title="📊 Swarm Aggregate Metrics", border_style="dim white", box=ROUNDED)

    # 3. Agent Wise Breakdown
    agent_stats = {}
    for r in records:
        name = r["agent_name"]
        if name not in agent_stats:
            agent_stats[name] = {
                "calls": 0,
                "cost": 0.0,
                "in": 0,
                "out": 0,
                "skeleton": 0,
                "skill": 0,
                "memory": 0,
                "tools": 0,
                "exec": 0,
            }
        bd = r.get("breakdown", {})
        agent_stats[name]["calls"] += 1
        agent_stats[name]["cost"] += r["cost"]
        agent_stats[name]["in"] += r["input_tokens"]
        agent_stats[name]["out"] += r["output_tokens"]
        agent_stats[name]["skeleton"] += bd.get("skeleton_tokens", 0)
        agent_stats[name]["skill"] += bd.get("skill_tokens", 0)
        agent_stats[name]["memory"] += bd.get("conversation_memory_tokens", 0)
        agent_stats[name]["tools"] += bd.get("tool_ledger_tokens", 0)
        agent_stats[name]["exec"] += bd.get("execution_report_tokens", 0)

    agent_table = Table(box=ROUNDED, border_style="dim white", expand=True)
    agent_table.add_column("Agent Name", style="bold cyan")
    agent_table.add_column("Calls", justify="center", style="white")
    agent_table.add_column("Cost (USD)", justify="right", style="bold green")
    agent_table.add_column("Input/Output", justify="right", style="dim white")
    agent_table.add_column("Memory Breakdown (Skeleton / Skill / Mem / Tools)", justify="left", style="yellow")

    for name, stats in agent_stats.items():
        total_parts = max(1, stats["skeleton"] + stats["skill"] + stats["memory"] + stats["tools"])
        
        # Build sparkline ratio representation
        sk_pct = int((stats["skeleton"] / total_parts) * 10)
        s_pct = int((stats["skill"] / total_parts) * 10)
        m_pct = int((stats["memory"] / total_parts) * 10)
        t_pct = int((stats["tools"] / total_parts) * 10)

        bar = (
            "█" * sk_pct + "░" * s_pct + "▒" * m_pct + "▓" * t_pct
        )
        bar_padded = bar.ljust(10)[:10]

        breakdown_text = f"[{bar_padded}] ({stats['skeleton']:,} / {stats['skill']:,} / {stats['memory']:,} / {stats['tools']:,})"

        agent_table.add_row(
            name,
            str(stats["calls"]),
            f"${stats['cost']:.5f}",
            f"{stats['in']:,} / {stats['out']:,}",
            breakdown_text
        )

    agent_pane = Panel(agent_table, title="🤖 Agent-Wise Consumption Metrics", border_style="cyan", box=ROUNDED)

    # 4. Turn-Wise Execution Log
    log_table = Table(box=ROUNDED, border_style="dim white", expand=True)
    log_table.add_column("Time", style="dim white")
    log_table.add_column("Agent", style="bold yellow")
    log_table.add_column("Type", justify="center")
    log_table.add_column("Model Used", style="dim cyan")
    log_table.add_column("Input/Output", justify="right")
    log_table.add_column("Turn Cost", justify="right", style="bold green")

    # Display last 8 records to prevent screen bloat
    for r in records[-8:]:
        purpose_lbl = "[bold red]ROUTER[/bold red]" if r["purpose"] == "router" else "[bold green]EXEC[/bold green]"
        log_table.add_row(
            r["timestamp"].split("T")[1].replace("Z", ""),
            r["agent_name"],
            purpose_lbl,
            r["model_name"],
            f"{r['input_tokens']:,} / {r['output_tokens']:,}",
            f"${r['cost']:.5f}"
        )

    log_pane = Panel(log_table, title="📜 Turn-Wise Real-Time Execution Log (Last 8 turns)", border_style="yellow", box=ROUNDED)

    # Assemble unified layout
    layout = Layout()
    layout.split_column(
        Layout(header, size=5),
        Layout(metrics_pane, size=6),
        Layout(agent_pane, ratio=2),
        Layout(log_pane, ratio=2),
    )
    return layout


def start_realtime_monitor(session_id: str):
    """Initializes the Live Rich Dashboard monitoring loop."""
    console = Console()
    console.clear()
    
    with Live(build_dashboard(session_id), refresh_per_second=2, screen=True) as live:
        try:
            while True:
                time.sleep(0.5)
                live.update(build_dashboard(session_id))
        except KeyboardInterrupt:
            console.clear()
            console.print("[bold yellow]👋 Stopped LangTrace real-time monitor.[/bold yellow]")
