import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import json
from core.models.agent_node import redis_client

data = redis_client.get("neuron:support_session:SupportRouter")
if data:
    d = json.loads(data.decode('utf-8'))
    print("KEYS IN NEURON DATA:", list(d.keys()))
    print("SYSTEM PROMPT LENGTH:", len(d.get('system_prompt', '')))
    print("SKILLS COUNT:", len(d.get('skills', [])))
else:
    print("No data found for neuron:support_session:SupportRouter")
    
role_data = redis_client.get("neuron_role:support_session:SupportRouter")
if role_data:
    try:
        r = json.loads(role_data.decode('utf-8'))
        print("ROLE SYSTEM PROMPT LENGTH:", len(r.get('system_prompt', '')))
    except Exception as e:
        print("Role data is raw str:", role_data.decode('utf-8'))
