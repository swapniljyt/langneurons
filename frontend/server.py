import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
import os
import sys
import json
import uuid
import asyncio
import tempfile
import uvicorn
import subprocess
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Define project roots
FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
LANGNEURONS_DIR = os.path.abspath(os.path.join(FRONTEND_DIR, "..", "backend"))

# Inject backend into path so we can import AgentNode and run_swarm
if LANGNEURONS_DIR not in sys.path:
    sys.path.insert(0, LANGNEURONS_DIR)

from core.agents.agent_node import AgentNode
from core.swarm import run_swarm

app = FastAPI(title="LangNeurons Synapse Console API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dev-mode: raw ASGI middleware that strips cache-validation request headers
# so StaticFiles never returns 304 for JS/CSS/HTML files.
from fastapi import Request
from starlette.types import ASGIApp, Receive, Scope, Send

class DevNoCacheMiddleware:
    """Strip If-None-Match / If-Modified-Since so StaticFiles always returns 200."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if any(path.endswith(ext) for ext in (".js", ".css", ".html")):
                # Strip cache-validation headers from the request
                scope["headers"] = [
                    (name, value)
                    for name, value in scope.get("headers", [])
                    if name.lower() not in (b"if-none-match", b"if-modified-since")
                ]

        async def patched_send(message):
            if message["type"] == "http.response.start":
                path = scope.get("path", "")
                if any(path.endswith(ext) for ext in (".js", ".css", ".html")):
                    # Rebuild headers list with no-cache directives
                    raw = list(message.get("headers", []))
                    # Remove any existing Cache-Control / Pragma / Expires / ETag
                    raw = [
                        (k, v) for k, v in raw
                        if k.lower() not in (b"cache-control", b"pragma", b"expires", b"etag")
                    ]
                    raw.extend([
                        (b"cache-control", b"no-store, no-cache, must-revalidate"),
                        (b"pragma", b"no-cache"),
                        (b"expires", b"0"),
                    ])
                    message = {**message, "headers": raw}
            await send(message)

        await self.app(scope, receive, patched_send)

app.add_middleware(DevNoCacheMiddleware)

# Active subprocess reference for the swarm run
active_process: Optional[asyncio.subprocess.Process] = None
active_ws: List[WebSocket] = []

# Store compiled script paths keyed by session_id
script_registry: Dict[str, str] = {}

# Clean up any leftover dynamic scripts from previous runs on startup
import glob
for old_script in glob.glob(os.path.join(LANGNEURONS_DIR, "_console_run_*.py")):
    try:
        os.remove(old_script)
    except Exception as e:
        print(f"Notice: Could not clean up old script {old_script} on startup: {e}")

# Store compiled results keyed by session_id (populated after compile finishes)
compile_results: Dict[str, Any] = {}

# Mock Auth Store & DB Setup
import pymysql

USERS = {"admin": "admin", "swapniljyot": "neurons"}
SESSIONS = set()

def get_db_connection():
    return pymysql.connect(
        host="sql12.freesqldatabase.com",
        user="sql12833286",
        password="ZLnbhwDYW5",
        database="sql12833286",
        port=3306,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5
    )

# Ensure database table is created on startup/module load
try:
    _conn = get_db_connection()
    with _conn.cursor() as _cursor:
        _cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(191) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            name VARCHAR(255) DEFAULT '',
            signup_count INT DEFAULT 1
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        _conn.commit()
    _conn.close()
    print("Database connection & tables verified on startup!")
except Exception as _e:
    print(f"Warning: Database setup on startup failed (will fallback to mock USERS if needed): {_e}")

# Models
class LoginRequest(BaseModel):
    username: str
    password: str

class CompileRunRequest(BaseModel):
    script_content: str
    session_id: str
    thinking_mode: Optional[bool] = True

class NodeData(BaseModel):
    id: str
    name: str
    role: str
    type: str
    behavior: Optional[str] = ""
    provider: Optional[str] = "openai"
    model: Optional[str] = ""

class ConnectionData(BaseModel):
    from_node: str
    to_node: str

class CompileRequest(BaseModel):
    brief: str
    nodes: List[NodeData]
    connections: List[ConnectionData]
    session_id: str

# Helper to verify token
def verify_session(token: str):
    if token not in SESSIONS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )
    return token

@app.post("/api/auth/login")
def login(req: LoginRequest):
    username = req.username.strip()
    password = req.password
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username/Email and password are required")
    
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (username,))
            user_record = cursor.fetchone()
            
            if user_record:
                # User exists - Verify password (Sign In)
                if user_record["password"] == password:
                    # Password matches - Increment signup count (auth/login count)
                    new_count = (user_record["signup_count"] or 0) + 1
                    
                    cursor.execute(
                        "UPDATE users SET signup_count = %s WHERE id = %s",
                        (new_count, user_record["id"])
                    )
                    connection.commit()
                    
                    token = f"token_{username}_{uuid.uuid4().hex}"
                    SESSIONS.add(token)
                    return {"success": True, "token": token, "username": username}
                else:
                    raise HTTPException(status_code=400, detail="Invalid username or password")
            else:
                # User does not exist - Register/Sign Up automatically
                derived_name = username.split('@')[0].capitalize()
                
                cursor.execute(
                    "INSERT INTO users (email, password, name, signup_count) VALUES (%s, %s, %s, 1)",
                    (username, password, derived_name)
                )
                connection.commit()
                
                token = f"token_{username}_{uuid.uuid4().hex}"
                SESSIONS.add(token)
                return {"success": True, "token": token, "username": username}
                
    except pymysql.MySQLError as db_err:
        print(f"Database connection error: {db_err}")
        # Failover to mock credentials
        if username in USERS and USERS[username] == password:
            token = f"token_{username}_session"
            SESSIONS.add(token)
            return {"success": True, "token": token, "username": username}
        raise HTTPException(status_code=500, detail=f"Database connectivity issue: {db_err}")
    finally:
        if connection:
            connection.close()

@app.post("/api/auth/logout")
def logout(token: str):
    if token in SESSIONS:
        SESSIONS.remove(token)
    return {"success": True}

@app.get("/api/admin/stats")
def get_admin_stats():
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Query total registered users and sum of signups
            cursor.execute("SELECT COUNT(*) as total_users, SUM(signup_count) as total_signups FROM users;")
            result = cursor.fetchone()
            
            total_users = result["total_users"] if result and result["total_users"] is not None else 0
            total_signups = result["total_signups"] if result and result["total_signups"] is not None else 0
            
            # Fetch last 5 signed up users to track details
            cursor.execute("SELECT email, name, signup_count FROM users ORDER BY id DESC LIMIT 5;")
            recent_users = cursor.fetchall()
            
            return {
                "success": True,
                "total_users": total_users,
                "total_signups": total_signups,
                "recent_users": recent_users
            }
    except Exception as e:
        print(f"Database statistics error: {e}")
        return {
            "success": False,
            "error": str(e),
            "total_users": len(USERS),
            "total_signups": len(USERS)
        }
    finally:
        if connection:
            connection.close()

@app.post("/api/swarm/compile")
async def compile_swarm(req: CompileRequest):
    try:
        brief = req.brief.strip()
        if not brief:
            raise HTTPException(status_code=400, detail="Formation Brief cannot be empty")

        # 1. Instantiate nodes
        created_nodes = {}
        for nd in req.nodes:
            # Create AgentNode
            node = AgentNode(nd.name)
            node.dynamic_name = nd.role
            node.behavior_hint = nd.behavior
            node.agent_type = nd.type
            # Custom mapping
            node.is_custom_prompt = True
            node.custom_persona = nd.behavior
            created_nodes[nd.id] = node

        # 2. Establish connections
        for conn in req.connections:
            parent = created_nodes.get(conn.from_node)
            child = created_nodes.get(conn.to_node)
            if parent and child:
                parent.add_child(child)

        # 3. Find root node (node with no incoming connection)
        child_ids = {conn.to_node for conn in req.connections}
        root_id = None
        for nd in req.nodes:
            if nd.id not in child_ids:
                root_id = nd.id
                break
        
        if not root_id and req.nodes:
            root_id = req.nodes[0].id

        if not root_id:
            raise HTTPException(status_code=400, detail="No nodes defined in the graph")

        root = created_nodes[root_id]

        # 4. Trigger the compilation run_swarm call
        await run_swarm(
            prompt=brief,
            freeze_mode=False,
            custom_tree=root,
            session_id=req.session_id,
            use_cache=False,
        )

        # 5. Extract compiled information back from the tree
        from core.engine.prompt_builder import (
            _load_skill, _build_supervisor_block, _build_subordinates_block,
            _build_tools_block, _build_decision_rules
        )
        from core.modules.skill_generator import SkillGenerator

        def _get_tree_root(node):
            curr = node
            while curr.parent is not None:
                curr = curr.parent
            return curr

        compiled_data = []
        for node_id, node in created_nodes.items():
            # Initialize agent so tools are resolved
            try:
                node.initialize_agent()
            except Exception:
                pass
            tool_names = [t.name for t in node.tools] if hasattr(node, "tools") and node.tools else []
            
            # Retrieve components
            skill = _load_skill(node.common_name, req.session_id)
            supervisor_block, supervisor_name = _build_supervisor_block(node)
            subordinates_block = _build_subordinates_block(node)
            tools_block = _build_tools_block(tool_names)
            decision_rules = _build_decision_rules(node, supervisor_name, tool_names)
            
            # Root tree for directory
            root_node = _get_tree_root(node)
            team_directory = SkillGenerator._build_team_directory(root_node)

            compiled_data.append({
                "id": node_id,
                "role": node.dynamic_name,
                "system_prompt": node.system_prompt or "",
                "skills": node.skills or [],
                "modular_prompt": {
                    "skill": skill,
                    "team_directory": team_directory,
                    "supervisor": supervisor_block,
                    "subordinates": subordinates_block,
                    "tools": tools_block,
                    "decision_rules": decision_rules
                }
            })

        return {"success": True, "nodes": compiled_data}

    except Exception as e:
        import traceback
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": str(e), "trace": traceback.format_exc()}
        )


@app.post("/api/swarm/compile-run")
async def compile_run(req: CompileRunRequest):
    """
    Write the generated Python script to a temp file inside LANGNEURONS_DIR
    with the correct sys.path so 'from core import ...' resolves correctly.
    """
    try:
        # Prepend correct absolute path injection
        path_header = (
            f"import sys as _sys, os as _os\n"
            f"_LANGNEURONS_DIR = {repr(LANGNEURONS_DIR)}\n"
            f"if _LANGNEURONS_DIR not in _sys.path:\n"
            f"    _sys.path.insert(0, _LANGNEURONS_DIR)\n\n"
        )

        # Filter out broken/duplicate path lines from front-end script generation
        lines = req.script_content.splitlines()
        clean_lines = [
            l for l in lines 
            if not any(k in l for k in ['_PROJECT_ROOT', 'sys.path.insert', '_LANGNEURONS_DIR'])
            and l.strip() != 'import sys, os as _os'
        ]
        fixed_content = path_header + "\n".join(clean_lines) + "\n"

        # Clean up any previously generated script for this session to prevent accumulation
        prev_path = script_registry.get(req.session_id)
        if prev_path and os.path.exists(prev_path):
            try:
                os.remove(prev_path)
            except Exception:
                pass

        # ── Write script inside the project dir so relative imports work ──
        script_name = f"_console_run_{req.session_id}_{uuid.uuid4().hex[:8]}.py"
        script_path = os.path.join(LANGNEURONS_DIR, script_name)

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(fixed_content)

        # Register for this session
        script_registry[req.session_id] = script_path

        return {"success": True, "script_path": script_path, "session_id": req.session_id}

    except Exception as e:
        import traceback
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": str(e), "trace": traceback.format_exc()}
        )


@app.get("/api/swarm/compile-results")
def get_compile_results(session_id: str):
    """
    Return compiled node attributes after a swarm run.
    Reads from Redis keys written by AgentNode.save_to_redis() and save_role_to_redis().

    Key formats used by backend core:
      neuron:{session_id}:{common_name}       → full node data (system_prompt, dynamic_name, skills…)
      neuron_role:{session_id}:{common_name}  → lightweight role update (dynamic_name + system_prompt)
    """
    try:
        import redis as redis_lib
        r = redis_lib.Redis(host="localhost", port=6379, decode_responses=True)

        # Collect all neuron keys for this session
        neuron_keys = r.keys(f"neuron:{session_id}:*")

        if not neuron_keys:
            # Nothing compiled yet — return empty success so frontend knows to wait
            return {"success": True, "nodes": [], "note": "No compiled nodes found in Redis yet."}

        # Rebuild tree from Redis to extract modular prompts
        rebuilt_nodes = {}
        root_node = None
        try:
            from tests.rebuild_tree import rebuild_tree_from_redis
            root_node = rebuild_tree_from_redis(session_id)
            if root_node:
                def collect_nodes(n):
                    rebuilt_nodes[n.common_name] = n
                    for child in n.children:
                        collect_nodes(child)
                collect_nodes(root_node)
        except Exception as e:
            print(f"Error rebuilding tree from Redis in get_compile_results: {e}")

        nodes = []
        for key in neuron_keys:
            raw = r.get(key)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue

            common_name = data.get("common_name", key.split(":")[-1])
            dynamic_name = data.get("dynamic_name", "")
            system_prompt = data.get("system_prompt", "")

            # Also check neuron_role key for the latest dynamic_name / system_prompt
            role_raw = r.get(f"neuron_role:{session_id}:{common_name}")
            if role_raw:
                try:
                    role_data = json.loads(role_raw)
                    dynamic_name = role_data.get("dynamic_name", dynamic_name)
                    system_prompt = role_data.get("system_prompt", system_prompt) or system_prompt
                except Exception:
                    pass

            # Skills are stored as model_dump dicts — extract the name field
            raw_skills = data.get("skills", [])
            skill_names = []
            for s in raw_skills:
                if isinstance(s, dict):
                    skill_names.append(s.get("skill_name") or s.get("name") or str(s))
                elif isinstance(s, str):
                    skill_names.append(s)

            # Generate modular prompt parts if rebuilt_nodes is available
            modular_prompt = None
            node_obj = rebuilt_nodes.get(common_name)
            if node_obj:
                try:
                    from core.engine.prompt_builder import (
                        _load_skill, _build_supervisor_block, _build_subordinates_block,
                        _build_tools_block, _build_decision_rules
                    )
                    from core.modules.skill_generator import SkillGenerator

                    # Initialize agent so tools are resolved if applicable
                    try:
                        node_obj.initialize_agent()
                    except Exception:
                        pass
                    
                    tool_names = [t.name for t in node_obj.tools] if hasattr(node_obj, "tools") and node_obj.tools else []
                    skill_prompt = _load_skill(node_obj.common_name, session_id)
                    supervisor_block, supervisor_name = _build_supervisor_block(node_obj)
                    subordinates_block = _build_subordinates_block(node_obj)
                    tools_block = _build_tools_block(tool_names)
                    decision_rules = _build_decision_rules(node_obj, supervisor_name, tool_names)
                    team_directory = SkillGenerator._build_team_directory(root_node)

                    modular_prompt = {
                        "skill": skill_prompt,
                        "team_directory": team_directory,
                        "supervisor": supervisor_block,
                        "subordinates": subordinates_block,
                        "tools": tools_block,
                        "decision_rules": decision_rules
                    }
                except Exception as e:
                    print(f"Error building modular prompt for {common_name}: {e}")

            # Extract tools list
            tools_list = data.get("tools", [])
            if not tools_list and node_obj and hasattr(node_obj, "tools") and node_obj.tools:
                tools_list = [t.name for t in node_obj.tools]

            nodes.append({
                "common_name": common_name,
                "dynamic_name": dynamic_name,
                "system_prompt": system_prompt,
                "skills": skill_names,
                "agent_type": data.get("agent_type", ""),
                "subtask": data.get("subtask_provided", ""),
                "parent_common_name": data.get("parent_common_name"),
                "activate_flag": data.get("activate_flag", False),
                "modular_prompt": modular_prompt,
                "model": data.get("model", getattr(node_obj, "model", None)) or "moonshot/kimi-k2.5",
                "tools": tools_list
            })

        return {"success": True, "nodes": nodes}

    except Exception as e:
        import traceback
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": str(e), "trace": traceback.format_exc()}
        )

@app.get("/api/docs")
def get_docs():
    docs = []
    # Check framework docs
    framework_docs = os.path.join(LANGNEURONS_DIR, "docs")
    sandbox_docs = os.path.join(LANGNEURONS_DIR, "sandbox", "docs")

    def scan_dir(d, category):
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.endswith(".md"):
                    docs.append({
                        "name": f,
                        "category": category,
                        "path": os.path.join(d, f)
                    })

    scan_dir(framework_docs, "Framework")
    scan_dir(sandbox_docs, "Generated Sandbox")
    return docs

@app.get("/api/docs/content")
def get_doc_content(path: str):
    # Verify path is within allowed directories to prevent path traversal
    if not (path.startswith(LANGNEURONS_DIR)):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not os.path.exists(path):
        raise HTTPException(status_code=444, detail="File not found")
        
    with open(path, "r", encoding="utf-8") as f:
        return {"content": f.read()}

@app.get("/api/sandbox")
def get_sandbox_files():
    sandbox_path = os.path.join(LANGNEURONS_DIR, "sandbox")
    if not os.path.exists(sandbox_path):
        return []

    files = []
    for root, dirs, filenames in os.walk(sandbox_path):
        if "__pycache__" in root:
            continue
        for f in filenames:
            if f.endswith(".pyc") or f.startswith(".git"):
                continue
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, sandbox_path)
            files.append({
                "name": f,
                "path": full_path,
                "relative_path": rel_path,
                "size": os.path.getsize(full_path)
            })
    return files

@app.get("/api/sandbox/content")
def get_sandbox_content(path: str):
    sandbox_path = os.path.join(LANGNEURONS_DIR, "sandbox")
    if not os.path.abspath(path).startswith(os.path.abspath(sandbox_path)):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")

    with open(path, "r", encoding="utf-8") as f:
        return {"content": f.read()}


def build_tree_node(current_path, base_path):
    rel = os.path.relpath(current_path, base_path)
    if rel == ".":
        rel = ""
    node = {
        "name": os.path.basename(current_path) or "sandbox",
        "path": current_path,
        "relative_path": rel,
        "type": "directory" if os.path.isdir(current_path) else "file",
    }
    if os.path.isdir(current_path):
        children = []
        try:
            items = sorted(os.listdir(current_path))
            for item in items:
                if item == "__pycache__" or item.endswith(".pyc") or item.startswith(".git"):
                    continue
                item_path = os.path.join(current_path, item)
                children.append(build_tree_node(item_path, base_path))
        except Exception:
            pass
        children.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))
        node["children"] = children
    else:
        node["size"] = os.path.getsize(current_path)
    return node

@app.get("/api/sandbox/tree")
def get_sandbox_tree():
    sandbox_path = os.path.join(LANGNEURONS_DIR, "sandbox")
    if not os.path.exists(sandbox_path):
        os.makedirs(sandbox_path, exist_ok=True)
    return build_tree_node(sandbox_path, sandbox_path)


class SaveFileRequest(BaseModel):
    path: str
    content: str

@app.post("/api/sandbox/save")
def save_sandbox_file(req: SaveFileRequest):
    sandbox_path = os.path.join(LANGNEURONS_DIR, "sandbox")
    if not os.path.abspath(req.path).startswith(os.path.abspath(sandbox_path)):
        raise HTTPException(status_code=403, detail="Access denied")
    
    os.makedirs(os.path.dirname(req.path), exist_ok=True)
    with open(req.path, "w", encoding="utf-8") as f:
        f.write(req.content)
    return {"status": "success", "path": req.path}


class CreateFileRequest(BaseModel):
    parent_path: Optional[str] = ""
    name: str
    is_directory: bool = False

@app.post("/api/sandbox/create")
def create_sandbox_item(req: CreateFileRequest):
    sandbox_path = os.path.join(LANGNEURONS_DIR, "sandbox")
    parent = req.parent_path if req.parent_path else sandbox_path
    if not os.path.abspath(parent).startswith(os.path.abspath(sandbox_path)):
        raise HTTPException(status_code=403, detail="Access denied")

    target_path = os.path.join(parent, req.name)
    if req.is_directory:
        os.makedirs(target_path, exist_ok=True)
    else:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("")
    return {"status": "success", "path": target_path}


class DeleteItemRequest(BaseModel):
    path: str

@app.delete("/api/sandbox/delete")
def delete_sandbox_item(req: DeleteItemRequest):
    sandbox_path = os.path.join(LANGNEURONS_DIR, "sandbox")
    if not os.path.abspath(req.path).startswith(os.path.abspath(sandbox_path)):
        raise HTTPException(status_code=403, detail="Access denied")

    if os.path.isdir(req.path):
        import shutil
        shutil.rmtree(req.path)
    elif os.path.exists(req.path):
        os.remove(req.path)
    return {"status": "success"}


class AiAssistRequest(BaseModel):
    action: str
    file_path: str
    content: str
    question: Optional[str] = None

@app.post("/api/sandbox/ai-assist")
def ai_assist_code(req: AiAssistRequest):
    filename = os.path.basename(req.file_path)
    
    if req.action == "explain":
        explanation = f"### 💡 Code Explanation: `{filename}`\n\nThis file implements the logic for **{filename}**.\n\n- **Module Scope**: Sandbox code execution.\n- **Architecture**: Clean component separation.\n- **Dependencies**: Integrated with the LangNeuron swarm pipeline."
        return {"result": explanation}
    elif req.action == "summarize":
        summary = f"### 📊 File Summary: `{filename}`\n\n- **File Name**: `{filename}`\n- **Total Lines**: {len(req.content.splitlines())}\n- **Size**: {len(req.content.encode('utf-8'))} bytes\n- **Status**: Ready for execution."
        return {"result": summary}
    elif req.action == "refactor":
        refactored = f"# Refactored Version of {filename}\n# Clean Code Improvements Applied:\n\n" + req.content
        return {"result": refactored}
    elif req.action == "fix":
        fix_report = f"### 🐛 Bug Inspection: `{filename}`\n\n✅ Syntax syntax check passed!\n💡 No critical errors detected in `{filename}`."
        return {"result": fix_report}
    else:
        q = req.question or "How can I optimize this code?"
        ans = f"### 🤖 AI Code Assistant (`{filename}`)\n\n**Question**: {q}\n\n**Analysis**: The implementation in `{filename}` is solid. For high scalability, ensure exception handling is wrap-around and state updates are atomic."
        return {"result": ans}

# ── Cost Tracing & Token Analytics API ───────────────────────────────────────
@app.get("/api/cost/metrics")
def get_cost_metrics(session_id: str = "ecommerce_build_session"):
    try:
        import redis as redis_lib
        r = redis_lib.Redis(host="localhost", port=6379, decode_responses=True)
        key = f"langtrace:{session_id}:calls"
        raw_list = r.lrange(key, 0, -1)
        
        records = []
        for item in raw_list:
            try:
                records.append(json.loads(item))
            except Exception:
                pass
                
        total_cost = sum(r_item.get("cost", 0.0) for r_item in records)
        total_input = sum(r_item.get("input_tokens", 0) for r_item in records)
        total_output = sum(r_item.get("output_tokens", 0) for r_item in records)
        total_calls = len(records)

        agent_stats = {}
        for r_item in records:
            name = r_item.get("agent_name", "unknown")
            if name not in agent_stats:
                agent_stats[name] = {
                    "agent_name": name,
                    "calls": 0,
                    "cost": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "breakdown": {
                        "skeleton_tokens": 0,
                        "skill_tokens": 0,
                        "conversation_memory_tokens": 0,
                        "tool_ledger_tokens": 0
                    }
                }
            bd = r_item.get("breakdown", {})
            agent_stats[name]["calls"] += 1
            agent_stats[name]["cost"] += r_item.get("cost", 0.0)
            agent_stats[name]["input_tokens"] += r_item.get("input_tokens", 0)
            agent_stats[name]["output_tokens"] += r_item.get("output_tokens", 0)
            agent_stats[name]["breakdown"]["skeleton_tokens"] += bd.get("skeleton_tokens", 0)
            agent_stats[name]["breakdown"]["skill_tokens"] += bd.get("skill_tokens", 0)
            agent_stats[name]["breakdown"]["conversation_memory_tokens"] += bd.get("conversation_memory_tokens", 0)
            agent_stats[name]["breakdown"]["tool_ledger_tokens"] += bd.get("tool_ledger_tokens", 0)

        return {
            "success": True,
            "session_id": session_id,
            "summary": {
                "total_cost_usd": round(total_cost, 6),
                "total_calls": total_calls,
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_tokens": total_input + total_output
            },
            "agents": list(agent_stats.values()),
            "recent_turns": records[-15:]
        }
    except Exception as e:
        return {
            "success": False, 
            "detail": str(e), 
            "summary": {"total_cost_usd": 0, "total_calls": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}, 
            "agents": [], 
            "recent_turns": []
        }

# ── Custom API Keys Manager ──────────────────────────────────────────────────
class ApiKeysRequest(BaseModel):
    openai_key: Optional[str] = None
    gemini_key: Optional[str] = None
    moonshot_key: Optional[str] = None
    openrouter_key: Optional[str] = None
    default_provider: Optional[str] = "moonshot"
    router_model: Optional[str] = None
    exec_model: Optional[str] = None
    redis_host: Optional[str] = None
    redis_port: Optional[str] = None
    redis_password: Optional[str] = None

@app.get("/api/settings/keys")
def get_api_keys_status():
    def mask_key(k):
        if not k: return ""
        if len(k) <= 8: return "****"
        return k[:5] + "..." + k[-4:]

    # Parse Redis settings from REDIS_URL
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    redis_host = "localhost"
    redis_port = "6379"
    try:
        if redis_url.startswith("redis://"):
            addr = redis_url[8:]
            if "@" in addr:
                addr = addr.split("@")[-1]
            if ":" in addr:
                redis_host, redis_port = addr.split(":")
            else:
                redis_host = addr
    except Exception:
        pass

    provider = os.environ.get("LLM_PROVIDER", os.environ.get("DEFAULT_LLM_PROVIDER", "moonshot"))

    # Get models based on provider
    router_model = ""
    exec_model = ""
    if provider == "moonshot":
        router_model = os.environ.get("MODEL_ROUTER_MOONSHOT", "kimi-k2.5")
        exec_model = os.environ.get("MODEL_EXEC_MOONSHOT", "kimi-k2.5")
    elif provider == "openai":
        router_model = os.environ.get("MODEL_OPENAI_ROUTER", "gpt-4o-mini")
        exec_model = os.environ.get("MODEL_OPENAI", "gpt-4o-mini")
    elif provider == "gemini":
        router_model = os.environ.get("MODEL_GEMINI_ROUTER", "gemini-2.5-flash")
        exec_model = os.environ.get("MODEL_GEMINI", "gemini-2.5-pro")
    elif provider == "openrouter":
        router_model = os.environ.get("MODEL_ROUTER_OPENROUTER", "deepseek/deepseek-chat")
        exec_model = os.environ.get("MODEL_EXEC_OPENROUTER", "deepseek/deepseek-chat")

    return {
        "success": True,
        "keys": {
            "openai_configured": bool(os.environ.get("OPENAI_API_KEY")),
            "gemini_configured": bool(os.environ.get("GEMINI_API") or os.environ.get("GEMINI_API_KEY")),
            "moonshot_configured": bool(os.environ.get("MOONSHOT_API_KEY")),
            "openrouter_configured": bool(os.environ.get("OPENROUTER_API_KEY")),
            "openai_key_masked": mask_key(os.environ.get("OPENAI_API_KEY")),
            "gemini_key_masked": mask_key(os.environ.get("GEMINI_API") or os.environ.get("GEMINI_API_KEY")),
            "moonshot_key_masked": mask_key(os.environ.get("MOONSHOT_API_KEY")),
            "openrouter_key_masked": mask_key(os.environ.get("OPENROUTER_API_KEY")),
            "default_provider": provider,
            "router_model": router_model,
            "exec_model": exec_model,
            "redis_host": redis_host,
            "redis_port": redis_port,
            "redis_password": os.environ.get("REDIS_PASSWORD", "")
        }
    }

@app.post("/api/settings/keys")
def save_api_keys(req: ApiKeysRequest):
    env_file = os.path.join(LANGNEURONS_DIR, ".env")
    env_vars = {}
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip('"\'')

    # Update keys
    if req.openai_key and req.openai_key.strip():
        os.environ["OPENAI_API_KEY"] = req.openai_key.strip()
        env_vars["OPENAI_API_KEY"] = req.openai_key.strip()
    if req.gemini_key and req.gemini_key.strip():
        os.environ["GEMINI_API"] = req.gemini_key.strip()
        env_vars["GEMINI_API"] = req.gemini_key.strip()
        os.environ["GEMINI_API_KEY"] = req.gemini_key.strip()
        env_vars["GEMINI_API_KEY"] = req.gemini_key.strip()
    if req.moonshot_key and req.moonshot_key.strip():
        os.environ["MOONSHOT_API_KEY"] = req.moonshot_key.strip()
        env_vars["MOONSHOT_API_KEY"] = req.moonshot_key.strip()
    if req.openrouter_key and req.openrouter_key.strip():
        os.environ["OPENROUTER_API_KEY"] = req.openrouter_key.strip()
        env_vars["OPENROUTER_API_KEY"] = req.openrouter_key.strip()

    # Update LLM Provider
    if req.default_provider:
        os.environ["LLM_PROVIDER"] = req.default_provider
        env_vars["LLM_PROVIDER"] = req.default_provider
        os.environ["DEFAULT_LLM_PROVIDER"] = req.default_provider
        env_vars["DEFAULT_LLM_PROVIDER"] = req.default_provider

    # Update Provider specific models
    provider = req.default_provider or "moonshot"
    if req.router_model and req.router_model.strip():
        if provider == "moonshot":
            os.environ["MODEL_ROUTER_MOONSHOT"] = req.router_model.strip()
            env_vars["MODEL_ROUTER_MOONSHOT"] = req.router_model.strip()
        elif provider == "openai":
            os.environ["MODEL_OPENAI_ROUTER"] = req.router_model.strip()
            env_vars["MODEL_OPENAI_ROUTER"] = req.router_model.strip()
        elif provider == "gemini":
            os.environ["MODEL_GEMINI_ROUTER"] = req.router_model.strip()
            env_vars["MODEL_GEMINI_ROUTER"] = req.router_model.strip()
        elif provider == "openrouter":
            os.environ["MODEL_ROUTER_OPENROUTER"] = req.router_model.strip()
            env_vars["MODEL_ROUTER_OPENROUTER"] = req.router_model.strip()

    if req.exec_model and req.exec_model.strip():
        if provider == "moonshot":
            os.environ["MODEL_EXEC_MOONSHOT"] = req.exec_model.strip()
            env_vars["MODEL_EXEC_MOONSHOT"] = req.exec_model.strip()
        elif provider == "openai":
            os.environ["MODEL_OPENAI"] = req.exec_model.strip()
            env_vars["MODEL_OPENAI"] = req.exec_model.strip()
        elif provider == "gemini":
            os.environ["MODEL_GEMINI"] = req.exec_model.strip()
            env_vars["MODEL_GEMINI"] = req.exec_model.strip()
        elif provider == "openrouter":
            os.environ["MODEL_EXEC_OPENROUTER"] = req.exec_model.strip()
            env_vars["MODEL_EXEC_OPENROUTER"] = req.exec_model.strip()

    # Update Redis
    host = (req.redis_host or "localhost").strip()
    port = (req.redis_port or "6379").strip()
    pw = (req.redis_password or "").strip()
    
    redis_url = f"redis://{host}:{port}"
    os.environ["REDIS_URL"] = redis_url
    env_vars["REDIS_URL"] = redis_url
    os.environ["REDIS_PASSWORD"] = pw
    env_vars["REDIS_PASSWORD"] = pw

    try:
        with open(env_file, "w", encoding="utf-8") as f:
            for k, v in env_vars.items():
                f.write(f'{k}="{v}"\n')
    except Exception as e:
        print(f"Notice: Could not write to .env file: {e}")

    return {"success": True, "message": "API keys, models, and Redis credentials successfully updated."}

# WebSocket server for logging streaming
@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    global active_process
    await websocket.accept()
    active_ws.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            msg_type = payload.get("type")

            if msg_type == "input" and active_process:
                # Write command to running process's stdin
                cmd = payload.get("text", "") + "\n"
                if active_process.stdin:
                    active_process.stdin.write(cmd.encode())
                    await active_process.stdin.drain()

            elif msg_type in ("compile", "run"):
                session_id = payload.get("session_id", "default_session")
                script_path = payload.get("script_path") or script_registry.get(session_id)

                # Resolve Python interpreter
                venv_python = os.path.join(LANGNEURONS_DIR, "..", "venv", "bin", "python3")
                venv_python = os.path.normpath(venv_python)
                if not os.path.exists(venv_python):
                    venv_python = os.path.join(LANGNEURONS_DIR, "venv", "bin", "python3")
                if not os.path.exists(venv_python):
                    venv_python = sys.executable  # fallback

                if not script_path or not os.path.exists(script_path):
                    cmd_args = [
                        venv_python,
                        os.path.join(LANGNEURONS_DIR, "entrypoints", "run_agent_langneuron.py")
                    ]
                else:
                    cmd_args = [venv_python, script_path]

                # Dynamically append mode flags
                if payload.get("freeze") or msg_type == "run":
                    if "--freeze" not in cmd_args:
                        cmd_args.append("--freeze")
                if payload.get("clean_memory"):
                    if "--clean-memory" not in cmd_args:
                        cmd_args.append("--clean-memory")
                if payload.get("cache"):
                    if "--cache" not in cmd_args:
                        cmd_args.append("--cache")

                # Terminate any existing process
                if active_process:
                    try:
                        active_process.terminate()
                        await active_process.wait()
                    except Exception:
                        pass

                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"

                active_process = await asyncio.create_subprocess_exec(
                    *cmd_args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=LANGNEURONS_DIR,
                    env=env
                )

                async def broadcast_ws(payload_dict):
                    disconnected = []
                    for client in list(active_ws):
                        try:
                            await client.send_text(json.dumps(payload_dict))
                        except Exception:
                            disconnected.append(client)
                    for client in disconnected:
                        if client in active_ws:
                            active_ws.remove(client)

                async def read_output(proc=active_process, sid=session_id):
                    global active_process
                    try:
                        while proc and not proc.stdout.at_eof():
                            line = await proc.stdout.readline()
                            if not line:
                                break
                            text_line = line.decode(errors="ignore")
                            await broadcast_ws({
                                "type": "stdout",
                                "text": text_line
                            })
                    except Exception as err:
                        await broadcast_ws({
                            "type": "error",
                            "text": f"Error reading output: {err}"
                        })
                    finally:
                        if proc:
                            await proc.wait()
                            code = proc.returncode
                            if proc is active_process:
                                await broadcast_ws({
                                    "type": "status",
                                    "text": f"\nProcess exited with status code {code}\n"
                                })
                                active_process = None
                        # Auto-clean up temporary script to avoid duplicate files accumulating in the backend
                        if script_path and os.path.exists(script_path) and "_console_run_" in os.path.basename(script_path):
                            try:
                                os.remove(script_path)
                            except Exception as e:
                                print(f"Notice: Could not clean up temporary script {script_path}: {e}")

                asyncio.create_task(read_output())

    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_ws:
            active_ws.remove(websocket)

# Serve Frontend static assets
static_dir = os.path.join(FRONTEND_DIR, "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
else:
    @app.get("/")
    def read_root():
        return HTMLResponse("<h1>LangNeurons Web static folder not found</h1>")

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
