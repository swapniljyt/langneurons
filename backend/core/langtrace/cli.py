"""
core/langtrace/cli.py
━━━━━━━━━━━━━━━━━━━━━
CLI Entrypoint for running the LangTrace analyzer.
"""

import argparse
from rich.console import Console

from .dashboard import start_realtime_monitor, build_dashboard, find_most_recent_session


def main():
    parser = argparse.ArgumentParser(description="LangTrace Real-Time Swarm LLM Cost Analyzer")
    parser.add_argument("--realtime", action="store_true", help="Start real-time live metrics monitor dashboard")
    parser.add_argument("--session", type=str, default="", help="Specific session ID to trace")
    args = parser.parse_args()

    session = args.session if args.session else find_most_recent_session()

    if args.realtime:
        start_realtime_monitor(session)
    else:
        # Static render print
        c = Console()
        c.print(build_dashboard(session))


if __name__ == "__main__":
    main()
