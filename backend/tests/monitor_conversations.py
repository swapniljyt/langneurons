import asyncio
import json
import time
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from core.agents.agent_node import redis_client

console = Console()

def get_active_conversations():
    """Scan Redis for all conversation keys"""
    keys = redis_client.keys("conversation:*")
    return [key.decode("utf-8") for key in keys]

def get_messages(key):
    """Get messages for a specific conversation key"""
    data = redis_client.get(key)
    if data:
        try:
            return json.loads(data.decode("utf-8"))
        except:
            return []
    return []

async def monitor_loop():
    """Main monitoring loop"""
    console.print("[bold green]👀  Starting Conversation Monitor...[/bold green]")
    console.print("[dim]Scanning for active agents... (Ctrl+C to stop)[/dim]\n")
    
    # Track the number of messages seen for each neuron
    # Format: { "conversation:neuron_1": 0, ... }
    seen_counts = {}
    
    while True:
        keys = get_active_conversations()
        
        for key in keys:
            messages = get_messages(key)
            current_count = len(messages)
            
            # Initialize seen count if new key
            if key not in seen_counts:
                seen_counts[key] = 0
                # Optionally print existing history or skip?
                # Let's print existing history to catch up
                seen_counts[key] = 0 
            
            # Check for new messages
            if current_count > seen_counts[key]:
                new_messages = messages[seen_counts[key]:]
                neuron_name = key.replace("conversation:", "")
                
                for msg in new_messages:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    
                    # Formatting
                    if role == "user" or role == "human":
                        # This is the "input" or trigger message
                        style = "bold cyan"
                        icon = "👤"
                        title = f"{icon} User -> {neuron_name}"
                    elif role == "ai" or role == "assistant":
                        # This is the agent response
                        style = "green"
                        icon = "🤖"
                        title = f"{icon} {neuron_name}"
                    else:
                        style = "white"
                        title = f"❓ {neuron_name} ({role})"
                    
                    panel = Panel(
                        content,
                        title=title,
                        border_style=style,
                        padding=(1, 2)
                    )
                    console.print(panel)
                    console.print(f"[dim]{time.strftime('%H:%M:%S')}[/dim]")
                
                # Update seen count
                seen_counts[key] = current_count
        
        await asyncio.sleep(2)

if __name__ == "__main__":
    try:
        asyncio.run(monitor_loop())
    except KeyboardInterrupt:
        console.print("\n[bold yellow]👋 Monitor stopped.[/bold yellow]")
