import sys, os
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import asyncio
import argparse
from core import run_swarm, AgentNode

SESSION_NAME = "naukri_job_broker_session"

FORMATION_BRIEF = """
You are the elite 10-Neuron Naukri Job Broker Swarm. Your mission is to continuously search, score, and apply to highly targeted tech roles on Naukri.com.
You operate under a strict 5-application throttle safety limit per execution and notify the user immediately on WhatsApp after every submission.

STRICT SEQUENTIAL FLOW:
  1. Feed Scraper (Neuron2) crawls the job search page.
  2. ATS Matcher (Neuron3) checks if candidate resume matches the JD.
  3. Batch Throttler (Neuron4) picks the top 5 matches and filters out applied jobs.
  4. Form Inspector (Neuron5) crawls the easy-apply popup to extract questions.
  5. Answer Draftsman (Neuron6) writes answers.
  6. Compliance Auditor (Neuron7) validates answer safety.
  7. PDF Compiler (Neuron8) creates the tailored resume PDF.
  8. Playwright Executor (Neuron9) logs in, completes inputs, and submits.
  9. WhatsApp Dispatcher (Neuron10) dispatches Twilio notification.
"""

def build_broker_tree() -> AgentNode:
    """
    Constructs the 10-Neuron Job Broker Swarm hierarchy.
    Each node is locked to its specific functional capability tier.
    """
    root = AgentNode("Neuron1", session_id=SESSION_NAME).set_agent_type("chat")
    
    n2 = AgentNode("Neuron2", session_id=SESSION_NAME).set_agent_type("researcher")
    n3 = AgentNode("Neuron3", session_id=SESSION_NAME).set_agent_type("analyst")
    n4 = AgentNode("Neuron4", session_id=SESSION_NAME).set_agent_type("runner")
    n5 = AgentNode("Neuron5", session_id=SESSION_NAME).set_agent_type("researcher")
    n6 = AgentNode("Neuron6", session_id=SESSION_NAME).set_agent_type("writer")
    n7 = AgentNode("Neuron7", session_id=SESSION_NAME).set_agent_type("analyst")
    n8 = AgentNode("Neuron8", session_id=SESSION_NAME).set_agent_type("writer")
    n9 = AgentNode("Neuron9", session_id=SESSION_NAME).set_agent_type("runner")
    n10 = AgentNode("Neuron10", session_id=SESSION_NAME).set_agent_type("chat")

    # Hook up hierarchical tree
    root.add_child(n2)
    root.add_child(n3)
    root.add_child(n4)
    root.add_child(n5)
    root.add_child(n6)
    root.add_child(n7)
    root.add_child(n8)
    root.add_child(n9)
    root.add_child(n10)
    
    return root

async def main():
    parser = argparse.ArgumentParser(description="LangNeurons — Naukri Job Broker Swarm")
    parser.add_argument(
        "--freeze",
        action="store_true",
        default=False,
        help="Freeze mode: execute existing tree from Redis and start execution."
    )
    parser.add_argument(
        "--clean-memory",
        action="store_true",
        default=False,
        help="Clear past execution history."
    )
    args = parser.parse_args()

    tree = build_broker_tree()
    await run_swarm(
        prompt=FORMATION_BRIEF,
        freeze_mode=args.freeze,
        custom_tree=tree,
        session_id=SESSION_NAME,
        clean_memory=args.clean_memory,
        thinking_mode=True
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
