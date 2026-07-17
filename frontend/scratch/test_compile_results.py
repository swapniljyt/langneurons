import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import json
import redis
from fastapi.testclient import TestClient
from server import app

def run_test():
    # 1. Setup local redis mock keys for session "test_session_123"
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)
    
    session_id = "test_session_123"
    common_name = "Router"
    
    # Clean up first
    r.delete(f"neuron:{session_id}:{common_name}")
    r.delete(f"neuron_role:{session_id}:{common_name}")
    
    neuron_data = {
        "session_id": session_id,
        "common_name": common_name,
        "dynamic_name": "task_coordinator",
        "subtask_provided": "Coordinate Westeros Kings research",
        "original_task": "Find information about Westeros Kings",
        "system_prompt": "Initial prompt",
        "activate_flag": True,
        "parent_common_name": None,
        "skills": [
            {
                "name": "research_coordination",
                "instructions": "Coordinate research tasks",
                "start_trigger": "User request",
                "end_condition": "Report delivered",
                "output_metadata_keys": []
            }
        ],
        "execution_stage": 0,
        "module_name": "",
        "agent_type": "researcher"
    }
    
    r.set(f"neuron:{session_id}:{common_name}", json.dumps(neuron_data))
    
    role_data = {
        "dynamic_name": "Westeros Historian",
        "system_prompt": "You are Westeros Historian..."
    }
    r.set(f"neuron_role:{session_id}:{common_name}", json.dumps(role_data))
    
    # 2. Test endpoint using FastAPI TestClient
    client = TestClient(app)
    response = client.get(f"/api/swarm/compile-results?session_id={session_id}")
    
    print("STATUS CODE:", response.status_code)
    results = response.json()
    print("RESPONSE JSON:")
    print(json.dumps(results, indent=2))
    
    # Clean up keys after test
    r.delete(f"neuron:{session_id}:{common_name}")
    r.delete(f"neuron_role:{session_id}:{common_name}")

if __name__ == "__main__":
    run_test()
