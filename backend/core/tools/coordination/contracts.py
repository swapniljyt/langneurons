"""
core/tools/coordination/contracts.py
──────────────────────────────────────
API contract publishing and reading.

Backend and database agents publish contracts describing their routes and schemas.
Frontend and integration agents read them to wire together without guessing.
"""

import os
import json
from langchain_core.tools import tool
from ..filesystem.read_write import SANDBOX_DIR

CONTRACT_PATH = os.path.join(SANDBOX_DIR, ".api_contracts.json")


@tool
def publish_contract(contracts_json: str) -> str:
    """
    Publishes API contracts to the shared team registry.
    Backend/Database agents MUST call this before writing implementation code.
    This informs frontend and integration agents exactly what API routes and schemas exist.

    Args:
        contracts_json: A JSON string describing your contracts. Example:
            {
              "routes": {"POST /auth/login": {"request": {"email": "str"}, "response": {"token": "str"}}},
              "db_schemas": {"users": ["id", "email", "hashed_password"]},
              "env_vars": ["OPENAI_API_KEY", "DATABASE_URL"]
            }
    """
    try:
        new_contracts = json.loads(contracts_json)
        existing = {}
        if os.path.exists(CONTRACT_PATH):
            with open(CONTRACT_PATH, 'r') as f:
                existing = json.load(f)
        for key, value in new_contracts.items():
            if key in existing and isinstance(existing[key], dict):
                existing[key].update(value)
            else:
                existing[key] = value
        with open(CONTRACT_PATH, 'w') as f:
            json.dump(existing, f, indent=2)
        return "✅ API contracts published. Frontend and integration agents can now read them via read_contracts()."
    except json.JSONDecodeError as e:
        return f"❌ Invalid JSON in contracts: {str(e)}"
    except Exception as e:
        return f"❌ Error publishing contracts: {str(e)}"


@tool
def read_contracts() -> str:
    """
    Reads the shared API contracts published by backend and database agents.
    Frontend and integration agents MUST call this before writing any code that
    connects to other services. This tells you exactly what API routes, schemas,
    and environment variables the backend team has defined.
    """
    try:
        if not os.path.exists(CONTRACT_PATH):
            return (
                "⚠️ No API contracts have been published yet. "
                "The backend team must call publish_contract() before the frontend can be wired."
            )
        with open(CONTRACT_PATH, 'r') as f:
            contracts = json.load(f)
        return f"📜 SHARED API CONTRACTS:\n{json.dumps(contracts, indent=2)}"
    except Exception as e:
        return f"❌ Error reading contracts: {str(e)}"
