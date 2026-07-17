"""
core/langtrace
━━━━━━━━━━━━━━
Real-time LLM cost and token consumption tracer package for the LangNeurons swarm.
"""

from .pricing import get_cost, count_tokens
from .callback import LangTraceCallbackHandler
from .dashboard import start_realtime_monitor, build_dashboard, find_most_recent_session
from .cli import main
