import sys, os as _os

_PROJECT_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

"""
run_agent_langneuron.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LangNeurons — Universal Swarm Entry Point.

HOW TO USE THIS FILE:
  1. Fill in FORMATION_BRIEF — plain language describing your swarm.
  2. Fill in SESSION_NAME — a unique identifier for this swarm's Redis state.
  3. Fill in SWARM_TREE — the agent hierarchy using generic neuron names.
     Assign agent_type from: chat | interviewer | writer | architect | researcher | analyst

The framework auto-generates:
  - Dynamic names (roles) per agent
  - Full system prompts per agent
  - Skill boundaries per agent
  - Sequential routing and state management

STEP 1 — Build and generate skills:
    python run_agent_langneuron.py

STEP 2 — Execute with chat:
    python run_agent_langneuron.py --freeze

STEP 3 — Reset memory and re-run:
    python run_agent_langneuron.py --freeze --clean-memory
"""

import asyncio
import argparse

# The clean public API facade!
from core import run_swarm, AgentNode


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 1 — SESSION NAME
# Give this swarm a unique name. Used as the Redis key for all state.
# Change this whenever you start a new type of swarm.
# ──────────────────────────────────────────────────────────────────────────────

SESSION_NAME = "ecommerce_build_session"   # ← CHANGE THIS


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2 — FORMATION BRIEF
# Write your swarm's purpose here in plain language.
# The LLM reads this and auto-generates every agent's skill, role, and behavior.
# Be specific about:
#   - What the swarm does (conversational? coding? research? data?)
#   - What each agent is responsible for
#   - What the sequential workflow looks like
#   - Any behavioral rules (e.g. "do NOT write files" or "always be formal")
# ──────────────────────────────────────────────────────────────────────────────


FORMATION_BRIEF = """
You are an elite, highly collaborative software engineering swarm. Your mission is to build a beautiful, professional e-commerce website themed around "Game of Thrones" from scratch.
The store is named "Westeros Treasures" or "The Iron Vault", selling premium items like Valyrian Steel Swords, Dragon Eggs, House Sigil Rings, Weirwood Tree Saplings, and Hand-Drawn Maps of Westeros.
You must design the architecture, implement the backend, build a stunning frontend, set up Docker/DevOps, and write/run tests to verify everything works.

WORKFLOW (strictly sequential):
  Phase 1 — Architecture & API Design:
    Design the e-commerce database schema (Products, Users, Orders).
    Define the API endpoints.
    Publish the API contracts to the team using the publish_contract tool so backend and frontend agree on the data structure.
    Save the architecture design to: docs/architecture.md

  Phase 2 — Backend Development:
    Read the contracts using read_contracts.
    Build a robust backend API (using FastAPI, Flask, or Node.js) that implements the agreed contracts.
    Include mock data for at least 5 Game of Thrones products (e.g. "Longclaw Valyrian Sword", "Rhaegal's Dragon Egg", "Lannister Sigil Ring", "House Stark Banner", "Hand of the King Pin") with images and prices.
    Save backend code to the backend/ directory.

  Phase 3 — Frontend Development:
    Read the contracts using read_contracts.
    Build a stunning, modern, and beautiful Game of Thrones themed frontend UI (HTML/CSS/JS) to display products and a shopping cart.
    The UI MUST be highly styled, responsive, and look extremely premium:
      - Aesthetic: Dark mode medieval theme. Use deep matte blacks (#0A0A0F), rich blood reds (#8B0000 or #5C0000), and gold accents (#D4AF37).
      - Typography: Use elegant serif typography (like Cinzel, Lora, or Playfair Display from Google Fonts) to invoke a legendary/epic atmosphere.
      - Elements: Glassmorphism cards with fine golden borders, subtle mist overlays, and noble hover animations.
    Ensure the frontend correctly calls the backend API to fetch products.
    Save frontend code to the frontend/ directory.

  Phase 4 — DevOps & Containerization:
    Create a Dockerfile and docker-compose.yml to run both the frontend and backend together.
    Run the application using the execute_command tool to ensure it starts successfully.
    Save configuration to the root directory.

  Phase 5 — Testing & QA:
    Write automated tests to verify the API returns products correctly.
    Run the tests using the execute_command tool.
    Fix any bugs if the tests fail.
    Generate a final test report in docs/test_report.md.

BEHAVIORAL RULES:
  - ALWAYS communicate interface designs using the contract tools (publish_contract, read_contracts) before writing code.
  - NEVER make up data formats; always refer to the published contracts.
  - The frontend MUST be beautiful and visually impressive. Don't use basic unstyled HTML.
  - Ensure all files are written to their respective directories.
  - Do not ask the human for help unless absolutely blocked. Complete the e-commerce site autonomously.

"""


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3 — SWARM TREE (hierarchy only)
# Define agent names and hierarchy here.
# Rules:
#   - Use generic names: Neuron1, Neuron2, ... OR descriptive role names.
#   - The framework assigns dynamic roles from FORMATION_BRIEF automatically.
#   - Set agent_type for each node (controls which tools they can use):
#       "chat"        → human interaction only (for root/router agents)
#       "interviewer" → human interaction + document parsing (for HR/conversational agents)
#       "writer"      → file read + write (for code/content writing agents)
#       "architect"   → file read + write + shell (for design/planning agents)
#       "researcher"  → file read + document parsing (for research/analysis agents)
#       "analyst"     → file read + shell execution (for data/analysis agents)
# ──────────────────────────────────────────────────────────────────────────────

def build_swarm_tree() -> AgentNode:
    """
    Define the agent hierarchy for your swarm.

    Replace the example below with your own tree shape.
    Use .add_child() to define the supervisor → subordinate relationships.

    Each AgentNode gets a common_name (your identifier, e.g. 'Neuron1') and
    a dynamic_name that is auto-generated during orchestration based on the skill
    assigned from the FORMATION_BRIEF. The dynamic_name is the agent's REAL
    identity (role title) and is always shown alongside the common_name.
    """

    # ── Hierarchical Multi-Tier Swarm (Root -> Leads -> Juniors) ───────────

    # Root agent — always the human-facing entry point
    root = AgentNode("Neuron1", session_id=SESSION_NAME)

    # First Tier: Functional Lead/Architect neurons
    architect_lead = AgentNode("Neuron2", session_id=SESSION_NAME)
    backend_lead = AgentNode("Neuron3", session_id=SESSION_NAME)
    frontend_lead = AgentNode("Neuron4", session_id=SESSION_NAME)
    devops_lead = AgentNode("Neuron5", session_id=SESSION_NAME)
    qa_lead = AgentNode("Neuron6", session_id=SESSION_NAME)

    # Second Tier: Junior Developers & Specialized Interns
    junior_architect_1 = AgentNode("Neuron7", session_id=SESSION_NAME)
    junior_architect_2 = AgentNode("Neuron14", session_id=SESSION_NAME)
    junior_db_dev = AgentNode("Neuron8", session_id=SESSION_NAME)
    junior_api_dev = AgentNode("Neuron9", session_id=SESSION_NAME)
    junior_ui_designer = AgentNode("Neuron10", session_id=SESSION_NAME)
    junior_fe_dev = AgentNode("Neuron11", session_id=SESSION_NAME)
    junior_devops_1 = AgentNode("Neuron12", session_id=SESSION_NAME)
    junior_devops_2 = AgentNode("Neuron15", session_id=SESSION_NAME)

    # ── Build hierarchy ───────────────────────────────────────────────────────
    
    # 1. Root connects to all main Division Leads
    root.add_child(architect_lead)
    root.add_child(backend_lead)
    root.add_child(frontend_lead)
    root.add_child(devops_lead)
    root.add_child(qa_lead)

    # 2. Architect Division Branching (2 children)
    architect_lead.add_child(junior_architect_1)
    architect_lead.add_child(junior_architect_2)

    # 3. Backend Division Branching (2 children)
    backend_lead.add_child(junior_db_dev)
    backend_lead.add_child(junior_api_dev)

    # 4. Frontend Division Branching (2 children)
    frontend_lead.add_child(junior_ui_designer)
    frontend_lead.add_child(junior_fe_dev)

    # 5. DevOps Division Branching (2 children)
    devops_lead.add_child(junior_devops_1)
    devops_lead.add_child(junior_devops_2)

    return root

    # ── Alternative: Flat 3-agent swarm (uncomment to use) ───────────────────
    # root   = AgentNode("Neuron1", session_id=SESSION_NAME)
    # worker = AgentNode("Neuron2", session_id=SESSION_NAME)
    # review = AgentNode("Neuron3", session_id=SESSION_NAME)
    # root.add_child(worker)
    # root.add_child(review)
    # return root


# ──────────────────────────────────────────────────────────────────────────────
# ENTRY POINT — no changes needed below this line
# ──────────────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="LangNeurons — Universal Swarm Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  Step 1 — build + generate skills:    python run_agent_langneuron.py\n"
            "  Step 1 — build (use cache if same):  python run_agent_langneuron.py --cache\n"
            "  Step 2 — run swarm (chat mode):      python run_agent_langneuron.py --freeze\n"
            "  Step 3 — reset memory + re-run:      python run_agent_langneuron.py --freeze --clean-memory\n"
        )
    )
    parser.add_argument(
        "--freeze",
        action="store_true",
        default=False,
        help="Freeze mode: load existing tree from Redis and start execution + chat.",
    )
    parser.add_argument(
        "--clean-memory",
        action="store_true",
        default=False,
        help="Clear past execution history for a fresh start (use with --freeze).",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        default=False,
        help=(
            "Cache mode (unfreeze only): if the FORMATION_BRIEF is IDENTICAL to the previous "
            "build, skip skill regeneration and reuse the existing Redis tree. "
            "If the brief changed, a full rebuild is triggered automatically. "
            "Ignored in --freeze mode."
        ),
    )
    args = parser.parse_args()

    custom_root = build_swarm_tree()

    await run_swarm(
        prompt=FORMATION_BRIEF,
        freeze_mode=args.freeze,
        custom_tree=custom_root,
        session_id=SESSION_NAME,
        clean_memory=args.clean_memory,
        thinking_mode=True,
        use_cache=args.cache,
    )



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Ctrl+C: graceful exit, 👋 Goodbye already printed by run_swarm
