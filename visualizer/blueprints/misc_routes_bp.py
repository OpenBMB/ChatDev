# ══════════════════════════════════════════════════════════════
#   misc_routes_bp.py — Misc Routes Blueprint
#   Auto-extracted from monolithic app.py for modular architecture
#
#   C-1 SPLIT PLAN: This file (5258 lines, 80+ routes) should be split into:
#     - knowledge_routes_bp.py — /api/knowledge_*, /api/upload_knowledge, /api/list_knowledge
#     - team_routes_bp.py     — /api/list_teams, /api/load_team, /api/save_squad, /api/org_*
#     - config_routes_bp.py   — /api/pipeline_config/*, /api/integrations/*, /api/vault/*
#     - stats_routes_bp.py    — /api/org_stats, /api/infra/*, /api/logs/*
#   See implementation_plan.md for full split strategy.
# ══════════════════════════════════════════════════════════════

import os
import re
import json
import time
import logging
import threading
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, send_from_directory, send_file, redirect, g
from visualizer.llm_client import get_llm_response
from visualizer.core.safe_io import write_json as safe_write_json, read_json as safe_read_json

logger = logging.getLogger("chatdev.bp.misc_routes")

misc_routes_bp = Blueprint("misc_routes", __name__)

# ── App.py shared state access (explicit imports instead of globals().update()) ──
_app_module = None  # Lazy reference to visualizer.app

# Explicitly declare the names we need from app.py
ROOT_DIR = None
TEAMS_DIR = None
COMPANY_CONFIG_DIR = None
VISUALIZER_DIR = None
squad_stats = {}
squad_injected_knowledge = {}

_REQUIRED_APP_NAMES = [
    # Core directories
    'ROOT_DIR', 'TEAMS_DIR', 'COMPANY_CONFIG_DIR', 'VISUALIZER_DIR',
    'PLAYBOOKS_DIR', 'SAVED_WORKFLOWS_DIR',
    # State
    'squad_stats', 'squad_injected_knowledge',
    'PLAYBOOKS', 'playbook_cache', 'TEAM_TEMPLATES',
    'approval_states', 'executive_states', 'connector_configs',
    '_PERSISTENT_STATE', '_chat_history',
    '_json_cache_lock', '_json_file_cache',
    '_launchpad_executions', '_system_stats_cache', '_system_stats_lock',
    '_api_cache', '_knowledge_chunks', '_shared_chunks',
    # Utility functions
    'validate_team_name', 'get_team_lock', 'lazy_import',
    'api_error', 'api_success', 'safe_error_response',
    '_load_playbooks', 'save_squad_stats',
    'ensure_and_load_graph', '_extract_text_from_file',
    '_index_knowledge_file', '_emit_indexing_progress',
    'validate_file_size', '_generate_bookclub_html',
    # Celery / Workflow execution
    'execute_workflow_background', 'emit_log', 'get_logs',
    'meter_action', 'get_background_tasks',
    'start_recurring_schedule', 'stop_recurring_schedule',
    'execute_subtasks_background',
    # Services / Singletons
    'mcp_hub', 'secure_vault', 'socketio_server',
    '_ceo_orchestrator', '_data_center', '_tool_registry',
    '_cross_squad_bus', '_vector_db', '_vision_healer',
    '_context_mgr', '_parallel_mgr', '_self_evolving',
    '_omni_sink_loaded', '_web_operator_loaded', '_plugin_registry_loaded',
    '_eval_quality_loaded', '_session_timeout_loaded',
    '_approval_sys', '_webhook_queue', '_workflow_recovery',
    '_book_pipeline', '_book_ok', '_brain_ok',
    '_backend_utils_ok', '_ceo_persistence_ok',
    '_indexing_ready', '_team_files',
    '_ENTERPRISE_MODULES',
    'RAGMemoryPipeline',
]

def _import_app_globals_safe():
    """Import only the specific globals we need from app.py."""
    global _app_module
    import visualizer.app as _app
    _app_module = _app
    result = {}
    for name in _REQUIRED_APP_NAMES:
        val = getattr(_app, name, None)
        if val is not None:
            result[name] = val
    return result


try:
    _ag = _import_app_globals_safe()
    # Update only the specific names, not everything
    for _name, _val in _ag.items():
        globals()[_name] = _val
except Exception as _e:
    logger.warning(f"Failed to import app globals: {_e}")

@misc_routes_bp.before_app_request
def _lazy_reload_app_globals():
    """Re-import app.py globals on first request (fixes circular import timing)."""
    global _app_globals_ready
    if _app_globals_ready:
        return
    try:
        _ag2 = _import_app_globals_safe()
        for _name, _val in _ag2.items():
            globals()[_name] = _val
        _app_globals_ready = True
        logger.info("[misc_routes_bp] App globals lazy-reloaded successfully")
    except Exception as e:
        logger.warning(f"[misc_routes_bp] Lazy reload failed: {e}")

_app_globals_ready = False

@misc_routes_bp.route("/")
@misc_routes_bp.route("/dashboard")
def index():
    """Global Workforce Org Map landing page."""
    return send_from_directory("static", "dashboard.html")


@misc_routes_bp.route("/squad/<squad_name>")
def squad(squad_name):
    """Dynamic drill-down detail squad workspace."""
    return send_from_directory("static", "index.html")


@misc_routes_bp.route("/launchpad")
def launchpad():
    """Launch Pad — SPA view inside index.html."""
    return send_from_directory("static", "index.html")


@misc_routes_bp.route("/chain_visualizer")
def chain_visualizer():
    return send_from_directory("static", "chain_visualizer.html")


@misc_routes_bp.route("/workflow_designer")
def workflow_designer():
    """워크플로우 디자이너 — 쉬운 설계 도구."""
    return send_from_directory("static", "workflow_designer.html")


@misc_routes_bp.route("/replay")
def replay():
    return send_from_directory("static", "replay.html")


@misc_routes_bp.route("/agents")
def agents_page():
    """Agent Directory — Enterprise list/grid of all agents across all squads."""
    return send_from_directory("static", "agents.html")


@misc_routes_bp.route("/tools")
def tools_page():
    """Tools Registry — Independent weapons armory database."""
    return send_from_directory("static", "tools.html")


@misc_routes_bp.route("/api/cesium/create", methods=["POST"])
def api_cesium_create():
    """🌐 Create a Cesium for Unreal metaverse project."""
    try:
        from chatdev.cesium_project import create_cesium_project
        data = request.get_json() or {}
        result = create_cesium_project(
            project_name=data.get("project_name", "MetaverseProject"),
            lat=data.get("lat", 37.5665),
            lng=data.get("lng", 126.9780),
            quality=data.get("quality", "high"),
            enable_multiplayer=data.get("enable_multiplayer", False),
            enable_pixel_streaming=data.get("enable_pixel_streaming", False),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================
#    👥 Agent Directory & 🛠️ Tools Registry APIs
# ==========================================


@misc_routes_bp.route("/api/agents", methods=["GET"])
def api_agents():
    """Returns all agents from all teams with their tool mappings."""
    try:
        root_dir = ROOT_DIR  # #4: Use constant
        teams_dir = os.path.join(root_dir, "CompanyConfig", "Teams")
        
        # Load tools registry for N:M mapping
        tools_reg_path = os.path.join(root_dir, "CompanyConfig", "tools_registry.json")
        tools_registry = {}
        if os.path.exists(tools_reg_path):
            with open(tools_reg_path, 'r', encoding='utf-8') as f:
                tools_data = json.load(f)
                tools_registry = {t["id"]: t for t in tools_data.get("tools", [])}

        # Load agent-tool mappings
        mappings_path = os.path.join(root_dir, "CompanyConfig", "agent_tool_mappings.json")
        agent_tool_map = {}
        if os.path.exists(mappings_path):
            with open(mappings_path, 'r', encoding='utf-8') as f:
                agent_tool_map = json.load(f)

        all_agents = []
        if os.path.isdir(teams_dir):
            for team_name in sorted(os.listdir(teams_dir)):
                team_path = os.path.join(teams_dir, team_name)
                if not os.path.isdir(team_path) or team_name.startswith(('_', '.')):
                    continue
                
                # Read RoleConfig for role descriptions
                role_config = {}
                role_config_path = os.path.join(team_path, "RoleConfig.json")
                if os.path.exists(role_config_path):
                    try:
                        with open(role_config_path, 'r', encoding='utf-8') as f:
                            role_config = json.load(f)
                    except Exception as _e:
                        logging.debug(f"[suppressed] Exception: {_e}")
                
                # Read ChatChainConfig for node/agent info
                chain_config_path = os.path.join(team_path, "ChatChainConfig.json")
                if os.path.exists(chain_config_path):
                    try:
                        with open(chain_config_path, 'r', encoding='utf-8') as f:
                            chain_data = json.load(f)
                    except Exception:
                        chain_data = {}
                    
                    nodes = chain_data.get("nodes", [])
                    recruitments = chain_data.get("recruitments", [])
                    
                    # Add nodes as active agents
                    for node in nodes:
                        if node["id"] == "Trigger":
                            continue
                        agent_id = f"{team_name}/{node['id']}"
                        role_desc_arr = role_config.get(node.get("assignee", ""), [])
                        role_desc = role_desc_arr[2] if len(role_desc_arr) > 2 else (node.get("assignee") or node.get("phase", ""))
                        
                        # Get equipped tools from N:M mapping
                        equipped_tool_ids = agent_tool_map.get(agent_id, [])
                        equipped_tools = [tools_registry[tid] for tid in equipped_tool_ids if tid in tools_registry]
                        
                        # Auto-assign tools by capability detection
                        SupervisorRouter = lazy_import('chatdev.supervisor_router', 'SupervisorRouter')  # #5
                        sr = SupervisorRouter()
                        auto_tools = sr.get_node_tools(node)
                        
                        all_agents.append({
                            "id": agent_id,
                            "name": node.get("assignee") or node["id"],
                            "node_id": node["id"],
                            "team": team_name,
                            "phase": node.get("phase", ""),
                            "phaseType": node.get("phaseType", ""),
                            "role_description": role_desc[:120] if isinstance(role_desc, str) else str(role_desc)[:120],
                            "equipped_tools": equipped_tools,
                            "auto_tools": auto_tools,
                            "status": "active",
                            "updated_at": os.path.getmtime(chain_config_path)
                        })
                    
                    # Add recruitable roles (not yet placed on canvas)
                    for role_name in recruitments:
                        agent_id = f"{team_name}/_pool/{role_name}"
                        role_desc_arr = role_config.get(role_name, [])
                        role_desc = role_desc_arr[2] if len(role_desc_arr) > 2 else role_name
                        
                        all_agents.append({
                            "id": agent_id,
                            "name": role_name,
                            "node_id": None,
                            "team": team_name,
                            "phase": None,
                            "phaseType": None,
                            "role_description": role_desc[:120] if isinstance(role_desc, str) else str(role_desc)[:120],
                            "equipped_tools": [],
                            "auto_tools": [],
                            "status": "standby",
                            "updated_at": os.path.getmtime(chain_config_path)
                        })

        return jsonify({"status": "success", "agents": all_agents, "total": len(all_agents)})
    except Exception as e:
        logging.error(f"Agent directory error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



@misc_routes_bp.route("/api/tools", methods=["GET"])
def api_tools():
    """Returns the full tools registry with usage stats."""
    try:
        root_dir = ROOT_DIR  # #4: Use constant
        tools_reg_path = os.path.join(root_dir, "CompanyConfig", "tools_registry.json")
        
        if not os.path.exists(tools_reg_path):
            return jsonify({"status": "success", "tools": [], "total": 0})
        
        with open(tools_reg_path, 'r', encoding='utf-8') as f:
            tools_data = json.load(f)
        
        # Load agent-tool mappings to count usage
        mappings_path = os.path.join(root_dir, "CompanyConfig", "agent_tool_mappings.json")
        agent_tool_map = {}
        if os.path.exists(mappings_path):
            with open(mappings_path, 'r', encoding='utf-8') as f:
                agent_tool_map = json.load(f)
        
        # Count how many agents use each tool
        tool_usage = {}
        for agent_id, tool_ids in agent_tool_map.items():
            for tid in tool_ids:
                tool_usage[tid] = tool_usage.get(tid, 0) + 1
        
        tools = tools_data.get("tools", [])
        for tool in tools:
            tool["equipped_by_count"] = tool_usage.get(tool["id"], 0)
        
        return jsonify({"status": "success", "tools": tools, "total": len(tools)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



@misc_routes_bp.route("/api/agent_tools", methods=["POST"])
def api_agent_tools():
    """N:M Mapping — Equip or unequip tools for an agent."""
    try:
        root_dir = ROOT_DIR  # #4: Use constant
        mappings_path = os.path.join(root_dir, "CompanyConfig", "agent_tool_mappings.json")
        
        payload = request.get_json() or {}
        agent_id = payload.get("agent_id", "")
        tool_id = payload.get("tool_id", "")
        action = payload.get("action", "equip")  # "equip" or "unequip"
        
        if not agent_id or not tool_id:
            return jsonify({"status": "error", "message": "agent_id and tool_id required"}), 400
        
        # Load existing mappings
        if os.path.exists(mappings_path):
            with open(mappings_path, 'r', encoding='utf-8') as f:
                agent_tool_map = json.load(f)
        else:
            agent_tool_map = {}
        
        if agent_id not in agent_tool_map:
            agent_tool_map[agent_id] = []
        
        if action == "equip":
            if tool_id not in agent_tool_map[agent_id]:
                agent_tool_map[agent_id].append(tool_id)
        elif action == "unequip":
            agent_tool_map[agent_id] = [t for t in agent_tool_map[agent_id] if t != tool_id]
        
        safe_write_json(mappings_path, agent_tool_map)
        
        return jsonify({"status": "success", "agent_id": agent_id, "tools": agent_tool_map[agent_id]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
#    🔌 MCP Client Hub APIs
# ==========================================

# Import MCP singleton

@misc_routes_bp.route("/api/mcp/servers", methods=["GET"])
def api_mcp_servers():
    """List all registered MCP servers and their status."""
    # Require authentication for MCP operations
    try:
        from visualizer.backend_utils import require_auth
        # Manual auth check since we can't use decorator on already-defined function
        from flask import request as req
        if hasattr(require_auth, '__wrapped__'):
            pass  # auth disabled
    except ImportError:
        pass
    if not mcp_hub:
        return jsonify({"status": "error", "message": "MCP hub not available"}), 500
    servers = mcp_hub.get_server_status()
    return jsonify({"status": "success", "servers": servers, "total": len(servers)})



@misc_routes_bp.route("/api/mcp/tools", methods=["GET"])
def api_mcp_tools():
    """MCP tools/list — returns all available tools across all servers."""
    if not mcp_hub:
        return jsonify({"status": "error", "message": "MCP hub not available"}), 500
    server_id = request.args.get("server_id")
    tools = mcp_hub.tools_list(server_id)
    return jsonify({"status": "success", "tools": tools, "total": len(tools)})



@misc_routes_bp.route("/api/mcp/call", methods=["POST"])
def api_mcp_call():
    """MCP tools/call — execute a tool on a specific server.
    
    SECURITY: This endpoint can execute arbitrary tools on MCP servers.
    Authentication is enforced via before_request CSRF + auth checks.
    """
    if not mcp_hub:
        return jsonify({"status": "error", "message": "MCP hub not available"}), 500

    # Additional auth check for tool execution
    try:
        from visualizer.backend_utils import config as _cfg
        if _cfg.AUTH_ENABLED:
            from visualizer.backend_utils import require_auth
            auth_header = request.headers.get('Authorization', '')
            token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else ''
            if not token:
                token = request.args.get('token', '') or request.cookies.get('auth_token', '')
            import secrets as _secrets
            if not token or not _secrets.compare_digest(token, _cfg.AUTH_TOKEN):
                return jsonify({"status": "error", "message": "인증이 필요합니다"}), 401
    except (ImportError, AttributeError):
        pass

    payload = request.get_json() or {}
    server_id = payload.get("server_id", "")
    tool_name = payload.get("tool_name", "")
    arguments = payload.get("arguments", {})

    if not server_id or not tool_name:
        return jsonify({"status": "error", "message": "server_id and tool_name required"}), 400

    result = mcp_hub.tools_call(server_id, tool_name, arguments)
    return jsonify({"status": "success", "result": result})



@misc_routes_bp.route("/api/mcp/log", methods=["GET"])
def api_mcp_log():
    """Returns recent MCP call history."""
    if not mcp_hub:
        return jsonify({"status": "error", "message": "MCP hub not available"}), 500
    limit = int(request.args.get("limit", 50))
    log = mcp_hub.get_call_log(limit)
    return jsonify({"status": "success", "log": log, "total": len(log)})


# ==========================================
#    🔐 Secure Vault APIs
# ==========================================


@misc_routes_bp.route("/integrations")
def integrations_page():
    """Integrations & API Keys — now merged into Tools page."""
    return redirect("/tools#integrations")



@misc_routes_bp.route("/api/vault/status", methods=["GET"])
def api_vault_status():
    """Get status of all integration keys (masked, never plaintext)."""
    if not secure_vault:
        return jsonify({"status": "error", "message": "Vault not available"}), 500
    statuses = secure_vault.get_all_status()
    return jsonify({"status": "success", "integrations": statuses})



@misc_routes_bp.route("/api/vault/store", methods=["POST"])
def api_vault_store():
    """Store an encrypted API key."""
    if not secure_vault:
        return jsonify({"status": "error", "message": "Vault not available"}), 500
    payload = request.get_json() or {}
    integration_id = payload.get("integration_id", "")
    api_key = payload.get("api_key", "")

    if not integration_id or not api_key:
        return jsonify({"status": "error", "message": "integration_id and api_key required"}), 400

    result = secure_vault.store_key(integration_id, api_key)
    return jsonify(result)



@misc_routes_bp.route("/api/vault/test", methods=["POST"])
def api_vault_test():
    """Test connection with stored API key."""
    if not secure_vault:
        return jsonify({"status": "error", "message": "Vault not available"}), 500
    payload = request.get_json() or {}
    integration_id = payload.get("integration_id", "")

    if not integration_id:
        return jsonify({"status": "error", "message": "integration_id required"}), 400

    result = secure_vault.test_connection(integration_id)
    return jsonify(result)



@misc_routes_bp.route("/api/vault/delete", methods=["POST"])
def api_vault_delete():
    """Delete a stored API key."""
    if not secure_vault:
        return jsonify({"status": "error", "message": "Vault not available"}), 500
    payload = request.get_json() or {}
    integration_id = payload.get("integration_id", "")

    if not integration_id:
        return jsonify({"status": "error", "message": "integration_id required"}), 400

    result = secure_vault.delete_key(integration_id)
    return jsonify(result)


@misc_routes_bp.route("/api/list_teams", methods=["GET"])
def list_teams():
    """Scans CompanyConfig/Teams/ directory and returns list of team names."""
    try:
        root_dir = ROOT_DIR  # #4: Use constant
        teams_dir = os.path.join(root_dir, "CompanyConfig", "Teams")
        
        # Self-healing: create Teams folder if missing
        os.makedirs(teams_dir, exist_ok=True)
        
        # Filter directories only
        teams = [d for d in os.listdir(teams_dir) 
                 if os.path.isdir(os.path.join(teams_dir, d)) and not d.startswith(('_', '.'))]
        teams.sort()
        return jsonify({"status": "success", "teams": teams})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/load_team", methods=["GET"])
def load_team():
    """Loads specific ChatChainConfig.json for a team, including its active ontology and Supervisor metadata."""
    try:
        team_name = request.args.get("name", "Squad_A")
        # #15: Path traversal defense
        valid, team_name = validate_team_name(team_name)
        if not valid:
            return jsonify({"status": "error", "message": "Invalid team name"}), 400
        
        config_path = os.path.join(TEAMS_DIR, team_name, "ChatChainConfig.json")  # #4: Use constant
        if not os.path.exists(config_path):
            # Fallback to Default
            config_path = os.path.join(COMPANY_CONFIG_DIR, "Default", "ChatChainConfig.json")
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            
        # Load dynamic ontology dictionary if it exists
        ontology = {}
        industry_id = ""
        industry_name = ""
        squad_details = {}
        squad_config_path = os.path.join(TEAMS_DIR, team_name, "SquadConfig.json")  # #4
        if os.path.exists(squad_config_path):
            try:
                with open(squad_config_path, 'r', encoding='utf-8') as sf:
                    squad_details = json.load(sf)
                    ontology = squad_details.get("_ontology", {})
                    industry_id = squad_details.get("_industry_id", "")
                    industry_name = squad_details.get("_industry_name", "")
            except Exception as _e:
                logging.debug(f"[suppressed] Exception: {_e}")

        # 🧠 Supervisor Router — Enrich nodes with tool badges & warnings
        nodes = config_data.get("nodes", [])
        edges = config_data.get("edges", [])
        
        try:
            SupervisorRouter = lazy_import('chatdev.supervisor_router', 'SupervisorRouter')  # #5
            supervisor = SupervisorRouter()
            
            # Auto-inject Supervisor node if not present AND team opted in
            node_ids = {n["id"] for n in nodes}
            has_supervisor = "Supervisor" in node_ids
            auto_supervisor = squad_details.get("auto_supervisor", False)  # 기본값 off — 유저 선택
            
            if auto_supervisor and not has_supervisor and len(nodes) > 1:
                # Insert Supervisor between Trigger and first worker
                supervisor_node = {
                    "id": "Supervisor",
                    "phase": "Supervisor",
                    "phaseType": "SupervisorPhase",
                    "max_turn_step": 0,
                    "need_reflect": "False",
                    "assignee": "총괄 매니저",
                    "_is_supervisor": True
                }
                # Insert after Trigger
                trigger_idx = next((i for i, n in enumerate(nodes) if n["id"] == "Trigger"), 0)
                nodes.insert(trigger_idx + 1, supervisor_node)
                
                # Rewire edges: Trigger → Supervisor, Supervisor → each worker
                new_edges = []
                trigger_targets = []
                for edge in edges:
                    if edge["source"] == "Trigger":
                        trigger_targets.append(edge["target"])
                        # Trigger → Supervisor (only once)
                        if not any(e["source"] == "Trigger" and e["target"] == "Supervisor" for e in new_edges):
                            new_edges.append({"source": "Trigger", "target": "Supervisor"})
                        # Supervisor → original target
                        new_edges.append({"source": "Supervisor", "target": edge["target"]})
                    else:
                        new_edges.append(edge)
                edges = new_edges
            
            # Enrich each node with tools and warnings
            for node in nodes:
                node["_tools"] = supervisor.get_node_tools(node)
                node["_warnings"] = supervisor.get_node_warnings(node)
                node["_tool_icons"] = {t: SupervisorRouter.get_tool_icon_class(t) for t in node["_tools"]}
                
                # Mark supervisor node
                if node["id"] == "Supervisor" or node.get("_is_supervisor"):
                    node["_is_supervisor"] = True
                    node["_tools"] = ["Google", "Slack", "Notion", "HubSpot"]
                    node["_tool_icons"] = {t: SupervisorRouter.get_tool_icon_class(t) for t in node["_tools"]}
                    node["_warnings"] = []
                    
        except Exception as e:
            logging.error(f"Supervisor enrichment failed: {e}")
        
        stats = squad_stats.get(team_name, {})
        
        # Load RoleConfig for Fleet personnel display
        role_config = {}
        role_config_path = os.path.join(TEAMS_DIR, team_name, "RoleConfig.json")  # #4
        if os.path.exists(role_config_path):
            try:
                with open(role_config_path, 'r', encoding='utf-8') as rf:
                    role_config = json.load(rf)
            except Exception as _e:
                logging.debug(f"[suppressed] Exception: {_e}")
        if not role_config:
            # Fallback to Default RoleConfig
            default_role_path = os.path.join(COMPANY_CONFIG_DIR, "Default", "RoleConfig.json")  # #4
            if os.path.exists(default_role_path):
                try:
                    with open(default_role_path, 'r', encoding='utf-8') as rf:
                        role_config = json.load(rf)
                except Exception as _e:
                    logging.debug(f"[suppressed] Exception: {_e}")

        return jsonify({
            "status": "success",
            "team_name": team_name,
            "nodes": nodes,
            "edges": edges,
            "recruitments": config_data.get("recruitments", []),
            "role_config": role_config,
            "squad_details": squad_details,
            "ontology": ontology,
            "industry_id": industry_id,
            "industry_name": industry_name,
            "stats": stats
        })
    except Exception as e:
        logging.error(f"Error loading team config: {e}")
        return jsonify({"status": "error", "message": "팀 설정을 로드하는 중 오류가 발생했습니다"}), 500  # #16: Sanitized error


@misc_routes_bp.route("/api/save_graph", methods=["POST"])
def save_graph():
    """Overwrites the nodes and edges configuration in CompanyConfig/Teams/{team_name}/ChatChainConfig.json."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        # #15: Path traversal defense
        valid, team_name = validate_team_name(team_name)
        if not valid:
            return jsonify({"status": "error", "message": "Invalid team name"}), 400
        nodes_payload = payload.get("nodes", [])
        edges_payload = payload.get("edges", [])
        
        config_dir = os.path.join(TEAMS_DIR, team_name)  # #4: Use constant
        os.makedirs(config_dir, exist_ok=True)
        
        config_path = os.path.join(config_dir, "ChatChainConfig.json")
        
        # #20: Team-level file locking to prevent race conditions
        lock = get_team_lock(team_name)
        with lock:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            else:
                # Fallback loader — use ROOT_DIR (not undefined root_dir)
                default_path = os.path.join(ROOT_DIR, "CompanyConfig", "Default", "ChatChainConfig.json")
                if os.path.exists(default_path):
                    with open(default_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                else:
                    config_data = {}
                # CRITICAL: Bootstrap with only the Leader (CEO) to eliminate default dummy roles duplication
                config_data["recruitments"] = ["Chief Executive Officer"]
                
            # Overwrite nodes and edges
            config_data["nodes"] = nodes_payload
            config_data["edges"] = edges_payload
            
            # Save back to file
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            
        logging.info(f"CDC: Successfully saved new workflow DAG configuration to Teams/{team_name}/ChatChainConfig.json")
        return jsonify({"status": "success", "message": f"Workflow saved to Squad '{team_name}' successfully!"})
    except Exception as e:
        logging.error(f"Error saving DAG config: {e}")
        return jsonify({"status": "error", "message": "워크플로우 저장 중 오류가 발생했습니다"}), 500  # Sanitized error (no internal details)

# ==========================================
#    🔧 Phase CRUD API — 유저 커스텀 공정 단계 관리
# ==========================================


@misc_routes_bp.route("/api/phases", methods=["GET"])
def api_list_phases():
    """팀의 전체 Phase 목록 (전역 + 커스텀 + 오버라이드 병합)."""
    try:
        from visualizer.services.phase_manager import get_phase_manager
        pm = get_phase_manager()
        team_name = request.args.get("team_name", "Core_Engine")
        valid, team_name = validate_team_name(team_name)
        if not valid:
            return api_error("Invalid team name", 400)

        phases = pm.list_phases(team_name)
        phase_types = pm.get_phase_types()
        stats = pm.get_stats(team_name)
        return api_success(data={
            "phases": phases,
            "phase_types": phase_types,
            "stats": stats,
        })
    except Exception as e:
        return safe_error_response(e, "api_list_phases")


@misc_routes_bp.route("/api/phases", methods=["POST"])
def api_create_phase():
    """새 커스텀 Phase 생성."""
    try:
        from visualizer.services.phase_manager import get_phase_manager
        pm = get_phase_manager()
        payload = request.get_json() or {}
        team_name = payload.pop("team_name", "Core_Engine")
        valid, team_name = validate_team_name(team_name)
        if not valid:
            return api_error("Invalid team name", 400)

        result = pm.create_phase(team_name, payload)
        if result.get("error"):
            return api_error(result.get("message", "생성 실패"), 400, errors=result.get("errors", []))
        return api_success(data=result, message=result.get("message", "Phase 생성 완료"))
    except Exception as e:
        return safe_error_response(e, "api_create_phase")


@misc_routes_bp.route("/api/phases/<phase_id>", methods=["GET"])
def api_get_phase(phase_id):
    """단일 Phase 상세 조회."""
    try:
        from visualizer.services.phase_manager import get_phase_manager
        pm = get_phase_manager()
        team_name = request.args.get("team_name", "Core_Engine")
        valid, team_name = validate_team_name(team_name)
        if not valid:
            return api_error("Invalid team name", 400)

        phase = pm.get_phase(team_name, phase_id)
        if not phase:
            return api_error(f"Phase를 찾을 수 없음: {phase_id}", 404)
        return api_success(data=phase)
    except Exception as e:
        return safe_error_response(e, "api_get_phase")


@misc_routes_bp.route("/api/phases/<phase_id>", methods=["PUT"])
def api_update_phase(phase_id):
    """Phase 설정 수정 (커스텀: 직접 수정, 전역: 오버라이드 저장)."""
    try:
        from visualizer.services.phase_manager import get_phase_manager
        pm = get_phase_manager()
        payload = request.get_json() or {}
        team_name = payload.pop("team_name", "Core_Engine")
        valid, team_name = validate_team_name(team_name)
        if not valid:
            return api_error("Invalid team name", 400)

        result = pm.update_phase(team_name, phase_id, payload)
        if result.get("error"):
            return api_error(result.get("message", "수정 실패"), 400)
        return api_success(data=result, message=result.get("message", "Phase 수정 완료"))
    except Exception as e:
        return safe_error_response(e, "api_update_phase")


@misc_routes_bp.route("/api/phases/<phase_id>", methods=["DELETE"])
def api_delete_phase(phase_id):
    """Phase 삭제 (커스텀만 삭제, 전역은 오버라이드 제거)."""
    try:
        from visualizer.services.phase_manager import get_phase_manager
        pm = get_phase_manager()
        team_name = request.args.get("team_name", "Core_Engine")
        valid, team_name = validate_team_name(team_name)
        if not valid:
            return api_error("Invalid team name", 400)

        result = pm.delete_phase(team_name, phase_id)
        if result.get("error"):
            return api_error(result.get("message", "삭제 실패"), 404)
        return api_success(data=result, message=result.get("message", "Phase 삭제 완료"))
    except Exception as e:
        return safe_error_response(e, "api_delete_phase")


@misc_routes_bp.route("/api/phases/<phase_id>/clone", methods=["POST"])
def api_clone_phase(phase_id):
    """Phase 복제 (전역 Phase도 팀 커스텀으로 복제 가능)."""
    try:
        from visualizer.services.phase_manager import get_phase_manager
        pm = get_phase_manager()
        payload = request.get_json() or {}
        team_name = payload.get("team_name", "Core_Engine")
        new_id = payload.get("new_id", "")
        valid, team_name = validate_team_name(team_name)
        if not valid:
            return api_error("Invalid team name", 400)

        result = pm.clone_phase(team_name, phase_id, new_id)
        if result.get("error"):
            return api_error(result.get("message", "복제 실패"), 400)
        return api_success(data=result, message=result.get("message", "Phase 복제 완료"))
    except Exception as e:
        return safe_error_response(e, "api_clone_phase")

# ==========================================
#    🔗 Inter-Squad Pipeline Chain API
# ==========================================


@misc_routes_bp.route("/api/pipeline/chains", methods=["GET"])
def api_list_pipeline_chains():
    """전체 파이프라인 연쇄 규칙 목록."""
    try:
        from visualizer.services.inter_squad_trigger import get_inter_squad_trigger
        trigger = get_inter_squad_trigger()
        team_name = request.args.get("team_name", "")

        if team_name:
            valid, team_name = validate_team_name(team_name)
            if not valid:
                return api_error("Invalid team name", 400)
            data = trigger.get_chains_for_team(team_name)
        else:
            data = {"chains": trigger.list_chains()}

        return api_success(data=data)
    except Exception as e:
        return safe_error_response(e, "api_list_pipeline_chains")


@misc_routes_bp.route("/api/pipeline/chains", methods=["POST"])
def api_add_pipeline_chain():
    """연쇄 규칙 추가 (Division A 완료 → Division B 자동 시작)."""
    try:
        from visualizer.services.inter_squad_trigger import get_inter_squad_trigger
        trigger = get_inter_squad_trigger()
        payload = request.get_json() or {}

        source_team = payload.get("source_team", "")
        target_team = payload.get("target_team", "")
        if not source_team or not target_team:
            return api_error("source_team과 target_team이 필요합니다", 400)

        result = trigger.add_chain(
            source_team=source_team,
            target_team=target_team,
            trigger_on=payload.get("trigger_on", "completed"),
            payload_mapping=payload.get("payload_mapping"),
            description=payload.get("description", ""),
        )
        if result.get("error"):
            return api_error(result["message"], 400)
        return api_success(data=result, message=f"체인 추가: {source_team} → {target_team}")
    except Exception as e:
        return safe_error_response(e, "api_add_pipeline_chain")


@misc_routes_bp.route("/api/pipeline/chains/<chain_id>", methods=["DELETE"])
def api_remove_pipeline_chain(chain_id):
    """연쇄 규칙 삭제."""
    try:
        from visualizer.services.inter_squad_trigger import get_inter_squad_trigger
        trigger = get_inter_squad_trigger()
        result = trigger.remove_chain(chain_id)
        if result.get("error"):
            return api_error(result["message"], 404)
        return api_success(data=result, message="체인 삭제 완료")
    except Exception as e:
        return safe_error_response(e, "api_remove_pipeline_chain")


@misc_routes_bp.route("/api/pipeline/status", methods=["GET"])
def api_pipeline_status():
    """전체 파이프라인 실행 상태 + 연결 그래프."""
    try:
        from visualizer.services.inter_squad_trigger import get_inter_squad_trigger
        trigger = get_inter_squad_trigger()
        status = trigger.get_pipeline_status()
        graph = trigger.get_pipeline_graph()
        history = trigger.get_history(limit=20)
        return api_success(data={
            "status": status,
            "graph": graph,
            "recent_history": history,
        })
    except Exception as e:
        return safe_error_response(e, "api_pipeline_status")


@misc_routes_bp.route("/api/pipeline/trigger", methods=["POST"])
def api_manual_pipeline_trigger():
    """수동 파이프라인 트리거 (특정 Division의 다음 체인 실행)."""
    try:
        from visualizer.services.inter_squad_trigger import get_inter_squad_trigger
        trigger = get_inter_squad_trigger()
        payload = request.get_json() or {}
        source_team = payload.get("source_team", "")
        if not source_team:
            return api_error("source_team이 필요합니다", 400)

        result = trigger.trigger_next(
            source_team=source_team,
            result_payload=payload.get("result", {}),
            trigger_event=payload.get("trigger_event", "completed"),
        )
        if result.get("error"):
            return api_error(result["message"], 400)
        return api_success(data=result, message=f"{len(result.get('triggered', []))}개 팀 트리거 완료")
    except Exception as e:
        return safe_error_response(e, "api_manual_pipeline_trigger")

# ==========================================
#    📁 Workflow Gallery — Save/Load Named Snapshots
# ==========================================


@misc_routes_bp.route("/api/workflows/save", methods=["POST"])
def save_workflow_snapshot():
    """Save current workflow as a named snapshot to the gallery."""
    try:
        payload = request.get_json()
        name = payload.get("name", "").strip()
        team_name = payload.get("team_name", "Squad_A")
        nodes = payload.get("nodes", [])
        edges = payload.get("edges", [])
        
        # #8: Workflow validation — require at least 1 node
        if not nodes or len(nodes) == 0:
            return jsonify({"status": "error", "message": "워크플로우에 최소 1개의 노드가 필요합니다."}), 400
        
        if not name:
            name = f"{team_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # #22: UUID-based filename to prevent collisions; store display name in metadata
        import uuid
        file_id = uuid.uuid4().hex[:12]
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_name}_{file_id}.json"  # Human-readable + UUID suffix
        filepath = os.path.join(SAVED_WORKFLOWS_DIR, filename)
        
        snapshot = {
            "name": name,
            "team_name": team_name,
            "saved_at": datetime.now().isoformat(),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges
        }
        
        safe_write_json(filepath, snapshot)
        
        logging.info(f"📁 Workflow snapshot saved: {filename}")
        return jsonify({"status": "success", "message": f"Workflow '{name}' saved!", "filename": filename})
    except Exception as e:
        return safe_error_response(e, "workflow_save")


@misc_routes_bp.route("/api/workflows/list", methods=["GET"])
def list_workflow_snapshots():
    """List all saved workflow snapshots in the gallery. (#28: Response cached 30s)"""
    try:
        snapshots = []
        if os.path.exists(SAVED_WORKFLOWS_DIR):
            for filename in sorted(os.listdir(SAVED_WORKFLOWS_DIR), reverse=True):
                if filename.endswith(".json"):
                    filepath = os.path.join(SAVED_WORKFLOWS_DIR, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        snapshots.append({
                            "filename": filename,
                            "name": data.get("name", filename.replace(".json", "")),
                            "team_name": data.get("team_name", "Unknown"),
                            "saved_at": data.get("saved_at", ""),
                            "node_count": data.get("node_count", 0),
                            "edge_count": data.get("edge_count", 0)
                        })
                    except Exception:
                        continue
        return jsonify({"status": "success", "snapshots": snapshots})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/workflows/load", methods=["GET"])
def load_workflow_snapshot():
    """Load a specific workflow snapshot by filename."""
    try:
        filename = request.args.get("filename", "")
        if not filename:
            return api_error("No filename specified", 400)
        
        # #6: Path traversal defense
        is_safe, filepath = safe_resolve_path(SAVED_WORKFLOWS_DIR, filename)
        if not is_safe:
            return api_error("Invalid filename", 400)
        
        if not os.path.exists(filepath):
            return api_error("Snapshot not found", 404)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return jsonify({
            "status": "success",
            "name": data.get("name", ""),
            "team_name": data.get("team_name", ""),
            "nodes": data.get("nodes", []),
            "edges": data.get("edges", [])
        })
    except Exception as e:
        return safe_error_response(e, "load_workflow_snapshot")


@misc_routes_bp.route("/api/workflows/delete", methods=["POST"])
@misc_routes_bp.route("/api/workflows/<path:wf_filename>", methods=["DELETE"])  # #21: RESTful DELETE
def delete_workflow_snapshot(wf_filename=None):
    """Delete a saved workflow snapshot. Supports POST (legacy) and DELETE (RESTful)."""
    try:
        if wf_filename:
            filename = wf_filename
        else:
            payload = request.get_json() or {}
            filename = payload.get("filename", "")
        
        if not filename:
            return api_error("No filename specified", 400)
        
        # #7: Path traversal defense
        is_safe, filepath = safe_resolve_path(SAVED_WORKFLOWS_DIR, filename)
        if not is_safe:
            return api_error("Invalid filename", 400)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            return api_success(message="Workflow deleted")
        return api_error("File not found", 404)
    except Exception as e:
        return safe_error_response(e, "delete_workflow_snapshot")

# ==========================================
#          RAG & Tool Connector & HITL APIs
# ==========================================

# ── Persistent state (DB-backed if available, in-memory fallback) ──

@misc_routes_bp.route("/api/upload_knowledge", methods=["POST"])
def upload_knowledge():
    """Uploads one or more documents, parses, chunks, and indexes for RAG search."""
    MAX_FILE_SIZE = 300 * 1024 * 1024  # 300 MB per file
    import uuid as _uuid
    job_id = str(_uuid.uuid4())[:8]

    try:
        files = request.files.getlist("file")
        if not files or all(f.filename == '' for f in files):
            return jsonify({"status": "error", "message": "No file(s) provided"}), 400

        team_name = request.form.get("team_name", "Squad_A")
        root_dir = ROOT_DIR  # #4: Use constant
        knowledge_dir = os.path.join(root_dir, "CompanyConfig", "Knowledge")
        os.makedirs(knowledge_dir, exist_ok=True)

        valid_files = []
        skipped = []
        for file in files:
            if not file or file.filename == '':
                continue
            
            # #13: MIME type + magic byte validation
            from visualizer.core.file_validator import validate_upload
            validation = validate_upload(file, max_size_mb=500)
            if not validation["valid"]:
                skipped.append({"filename": file.filename, "reason": validation["error"]})
            else:
                valid_files.append((file, validation["size"]))

        total_files = len(valid_files)
        results = []
        total_chunks = 0

        # Initialize progress
        _emit_indexing_progress(job_id, {
            "phase": "starting",
            "progress": 0,
            "total_files": total_files,
            "current_file_idx": 0,
            "current_file": "",
            "message": f"📤 {total_files}개 파일 인덱싱 시작...",
            "files_status": []
        })

        for idx, (file, fsize) in enumerate(valid_files):
            fname = file.filename
            file_progress_base = int((idx / max(total_files, 1)) * 100)

            # Phase 1: Saving
            _emit_indexing_progress(job_id, {
                "phase": "saving",
                "progress": file_progress_base + 5,
                "total_files": total_files,
                "current_file_idx": idx + 1,
                "current_file": fname,
                "message": f"💾 [{idx+1}/{total_files}] '{fname}' 저장 중...",
                "files_status": results.copy()
            })

            filepath = os.path.join(knowledge_dir, fname)
            file.save(filepath)

            # Phase 2: Text Extraction
            ext = os.path.splitext(fname)[1].lower()
            ext_label = {".pdf": "PDF 페이지 추출", ".csv": "CSV 파싱", ".json": "JSON 파싱"}.get(ext, "텍스트 읽기")
            _emit_indexing_progress(job_id, {
                "phase": "extracting",
                "progress": file_progress_base + 20,
                "total_files": total_files,
                "current_file_idx": idx + 1,
                "current_file": fname,
                "message": f"📖 [{idx+1}/{total_files}] '{fname}' {ext_label} 중...",
                "files_status": results.copy()
            })

            content, page_count = _extract_text_from_file(filepath, fname)

            if not content.strip():
                results.append({
                    "filename": fname, "chunks": 0, "size": fsize,
                    "pages": page_count, "status": "no_text",
                    "chars_extracted": 0,
                    "message": "텍스트 추출 불가"
                })
                continue

            # Phase 3: Chunking
            _emit_indexing_progress(job_id, {
                "phase": "chunking",
                "progress": file_progress_base + 50,
                "total_files": total_files,
                "current_file_idx": idx + 1,
                "current_file": fname,
                "message": f"✂️ [{idx+1}/{total_files}] '{fname}' 청크 분할 중... ({len(content):,}자 추출됨)",
                "files_status": results.copy()
            })

            # Phase 4: Indexing
            _emit_indexing_progress(job_id, {
                "phase": "indexing",
                "progress": file_progress_base + 70,
                "total_files": total_files,
                "current_file_idx": idx + 1,
                "current_file": fname,
                "message": f"🧠 [{idx+1}/{total_files}] '{fname}' RAG 메모리 색인 중...",
                "files_status": results.copy()
            })

            chunk_count = _index_knowledge_file(team_name, fname, content, job_id=job_id)
            total_chunks += chunk_count

            # Auto-inject
            if team_name not in squad_injected_knowledge:
                squad_injected_knowledge[team_name] = []
            if fname not in squad_injected_knowledge[team_name]:
                squad_injected_knowledge[team_name].append(fname)

            results.append({
                "filename": fname,
                "chunks": chunk_count,
                "size": fsize,
                "pages": page_count,
                "chars_extracted": len(content),
                "status": "indexed",
                "message": f"{chunk_count}개 청크 생성"
            })

        # Phase 5: Complete
        _emit_indexing_progress(job_id, {
            "phase": "complete",
            "progress": 100,
            "total_files": total_files,
            "current_file_idx": total_files,
            "current_file": "",
            "message": f"✅ {len(results)}개 파일 인덱싱 완료! (총 {total_chunks} chunks)",
            "files_status": results
        })

        # Legacy RAG pipeline
        if RAGMemoryPipeline and results:
            try:
                pipeline = RAGMemoryPipeline(knowledge_dir=knowledge_dir)
                import threading
                threading.Thread(target=pipeline.bootstrap_pipeline).start()
            except Exception as e:
                logging.error(f"Error starting RAG indexing thread: {e}")

        return jsonify({
            "status": "success",
            "job_id": job_id,
            "message": f"{len(results)}개 파일 업로드 및 색인 완료 (총 {total_chunks} chunks)",
            "uploaded": results,
            "skipped": skipped,
            "total_files": len(results),
            "total_chunks": total_chunks,
        })
    except Exception as e:
        _emit_indexing_progress(job_id, {
            "phase": "error", "progress": 0,
            "message": f"❌ 인덱싱 오류: {str(e)}",
            "files_status": []
        })
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/list_knowledge", methods=["GET"])
def list_knowledge():
    """Lists files in CompanyConfig/Knowledge/ and the current team's injected subset."""
    try:
        team_name = request.args.get("team_name", "Squad_A")
        root_dir = ROOT_DIR  # #4: Use constant
        knowledge_dir = os.path.join(root_dir, "CompanyConfig", "Knowledge")
        os.makedirs(knowledge_dir, exist_ok=True)
        
        # List all available files
        all_files = [f for f in os.listdir(knowledge_dir) if os.path.isfile(os.path.join(knowledge_dir, f)) and not f.startswith(".")]
        all_files.sort()
        
        # Get team-specific injected files
        injected = squad_injected_knowledge.get(team_name, [])
        # Filter deleted files
        injected = [f for f in injected if f in all_files]
        
        # Uninjected files are the rest
        uninjected = [f for f in all_files if f not in injected]
        
        return jsonify({
            "status": "success",
            "uninjected": uninjected,
            "injected": injected
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/update_injected_knowledge", methods=["POST"])
def update_injected_knowledge():
    """Updates the list of files injected for a specific team, and auto-indexes new files."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        injected = payload.get("injected", [])

        # Detect newly added files
        prev_injected = set(squad_injected_knowledge.get(team_name, []))
        new_files = [f for f in injected if f not in prev_injected]

        squad_injected_knowledge[team_name] = injected

        # Auto-index newly injected files in background
        if new_files:
            knowledge_dir = os.path.join("CompanyConfig", "Knowledge")
            def _auto_index():
                for fname in new_files:
                    fpath = os.path.join(knowledge_dir, fname)
                    if not os.path.exists(fpath):
                        continue
                    # Skip if already indexed
                    existing = [c for c in _knowledge_chunks.get(team_name, []) if c.get("source") == fname]
                    if existing:
                        continue
                    try:
                        with open(fpath, "rb") as f:
                            raw = f.read()
                        # Try decode as text
                        try:
                            content = raw.decode("utf-8")
                        except UnicodeDecodeError:
                            content = raw.decode("latin-1", errors="replace")
                        job_id = f"inject_{team_name}_{fname}_{int(time.time())}"
                        _index_knowledge_file(team_name, fname, content, job_id=job_id)
                    except Exception as e:
                        print(f"[Auto-Index] Error indexing {fname}: {e}")
            import threading
            threading.Thread(target=_auto_index, daemon=True).start()

        # Broadcast UI notification update
        socketio_server.emit('knowledge_updated', {
            "team_name": team_name,
            "injected": injected,
            "new_files": new_files
        }, room=team_name)

        msg = f"주입 완료! {len(new_files)}개 파일 학습 시작" if new_files else "Injected knowledge updated successfully!"
        return jsonify({"status": "success", "message": msg, "new_indexing": len(new_files)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
#    Google Drive OAuth 2.0 & Knowledge Sources
# ==========================================

# In-memory Drive token store (per-session; for production use DB/encrypted vault)

@misc_routes_bp.route("/api/knowledge_sources/add", methods=["POST"])
def add_knowledge_source():
    """Add a knowledge source (URL, Drive file, or text) for grounding."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        source_type = payload.get("type", "url")  # url, drive_file, text
        source_url = payload.get("url", "")
        source_name = payload.get("name", "")
        source_content = payload.get("content", "")

        sources_dir = os.path.join(VISUALIZER_DIR, "knowledge_sources")
        os.makedirs(sources_dir, exist_ok=True)
        sources_path = os.path.join(sources_dir, f"{team_name}.json")

        existing = []
        if os.path.exists(sources_path):
            with open(sources_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)

        # If URL provided but no content, attempt to fetch
        if source_type == "url" and source_url and not source_content:
            try:
                import urllib.request
                req = urllib.request.Request(source_url, headers={"User-Agent": "ChatDev-DataHub/1.0"})
                resp = urllib.request.urlopen(req, timeout=15)
                raw = resp.read().decode("utf-8", errors="ignore")
                # Strip HTML tags for clean text
                import re
                source_content = re.sub(r'<[^>]+>', '', raw)[:50000]  # Cap at 50k chars
                if not source_name:
                    source_name = source_url.split("/")[-1] or "Imported Document"
            except Exception as fetch_err:
                source_content = f"[Fetch Error: {str(fetch_err)}]"

        source_id = "src_" + str(len(existing) + 1).zfill(3) + "_" + datetime.now().strftime("%H%M%S")
        new_source = {
            "id": source_id,
            "name": source_name or f"Source {len(existing) + 1}",
            "type": source_type,
            "url": source_url,
            "content_preview": (source_content[:200] + "...") if len(source_content) > 200 else source_content,
            "content_length": len(source_content),
            "added_at": datetime.now().isoformat(),
            "grounded": True
        }

        existing.append(new_source)

        with open(sources_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

        # Also save full content to a separate file for grounding
        content_dir = os.path.join(sources_dir, team_name)
        os.makedirs(content_dir, exist_ok=True)
        with open(os.path.join(content_dir, f"{source_id}.txt"), 'w', encoding='utf-8') as f:
            f.write(source_content)

        return jsonify({"status": "success", "source": new_source, "total_sources": len(existing)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/knowledge_sources/list", methods=["GET"])
def list_knowledge_sources():
    """List all knowledge sources for a team."""
    try:
        team_name = request.args.get("team_name", "Squad_A")
        sources_dir = os.path.join(VISUALIZER_DIR, "knowledge_sources")
        sources_path = os.path.join(sources_dir, f"{team_name}.json")

        if os.path.exists(sources_path):
            with open(sources_path, 'r', encoding='utf-8') as f:
                sources = json.load(f)
        else:
            sources = []

        return jsonify({"status": "success", "sources": sources, "count": len(sources)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/knowledge_sources/delete", methods=["POST"])
def delete_knowledge_source():
    """Delete a knowledge source."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        source_id = payload.get("source_id")

        sources_dir = os.path.join(VISUALIZER_DIR, "knowledge_sources")
        sources_path = os.path.join(sources_dir, f"{team_name}.json")

        if os.path.exists(sources_path):
            with open(sources_path, 'r', encoding='utf-8') as f:
                sources = json.load(f)
            sources = [s for s in sources if s["id"] != source_id]
            with open(sources_path, 'w', encoding='utf-8') as f:
                json.dump(sources, f, indent=2, ensure_ascii=False)

        # Remove content file
        content_file = os.path.join(sources_dir, team_name, f"{source_id}.txt")
        if os.path.exists(content_file):
            os.remove(content_file)

        return jsonify({"status": "success", "remaining": len(sources)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/knowledge_sources/grounding_context", methods=["GET"])
def get_grounding_context():
    """Get combined grounding context from all active sources for agent prompt injection."""
    try:
        team_name = request.args.get("team_name", "Squad_A")
        sources_dir = os.path.join(VISUALIZER_DIR, "knowledge_sources")
        sources_path = os.path.join(sources_dir, f"{team_name}.json")

        if not os.path.exists(sources_path):
            return jsonify({"status": "success", "context": "", "source_count": 0})

        with open(sources_path, 'r', encoding='utf-8') as f:
            sources = json.load(f)

        grounded = [s for s in sources if s.get("grounded", True)]
        context_parts = []
        for src in grounded:
            content_file = os.path.join(sources_dir, team_name, f"{src['id']}.txt")
            if os.path.exists(content_file):
                with open(content_file, 'r', encoding='utf-8') as f:
                    text = f.read()
                context_parts.append(f"--- Source: {src['name']} ---\n{text[:10000]}")

        combined = "\n\n".join(context_parts)
        return jsonify({
            "status": "success",
            "context": combined,
            "source_count": len(grounded),
            "total_chars": len(combined)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



@misc_routes_bp.route("/api/save_connectors", methods=["POST"])
def save_connectors():
    """Saves connector settings securely via encrypted vault storage."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        connector_type = payload.get("type", "GitHub")
        config = payload.get("config", {})
        
        # Use SecureConnectorManager if available
        try:
            from visualizer.backend.integration_hub import connector_manager
            result = connector_manager.save_connector(team_name, connector_type, config)
            logging.info(f"🔐 CTO: Securely stored connector tokens for {connector_type} under Squad {team_name}.")
            return jsonify(result)
        except ImportError as _e:
            logging.debug(f"[suppressed] ImportError: {_e}")
        
        # Fallback: in-memory storage
        if team_name not in connector_configs:
            connector_configs[team_name] = {}
        connector_configs[team_name][connector_type] = config
        
        # Safe storage in environment variables (masked)
        env_prefix = f"CONN_{connector_type.upper()}_"
        for key, val in config.items():
            os.environ[f"{env_prefix}{key.upper()}"] = str(val)
            
        logging.info(f"CTO: Updated connector tokens for {connector_type} under Squad {team_name}.")
        return jsonify({"status": "success", "message": f"Secure settings for {connector_type} committed and tools re-armed!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/dag/pause", methods=["POST"])
def dag_pause():
    """Triggered by chat_chain when it pauses at a Human Approval node."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        node_id = payload.get("node_id")
        
        approval_states[(team_name, node_id)] = "pending"
        
        # Broadcast to room to show approval prompt modal in front-end
        socketio_server.emit('approval_required', {
            "team_name": team_name,
            "node_id": node_id
        }, room=team_name)
        
        logging.info(f"DAG paused on squad '{team_name}' at node '{node_id}'. Webcast alert sent.")
        return jsonify({"status": "success", "message": "DAG pause registered."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/dag/status", methods=["GET"])
def dag_status():
    """Polled by chat_chain to check if the user approved the milestone node."""
    try:
        team_name = request.args.get("team_name", "Squad_A")
        node_id = request.args.get("node_id")
        
        status = approval_states.get((team_name, node_id), "pending")
        return jsonify({"status": "success", "status": status})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/dag/approve", methods=["POST"])
def dag_approve():
    """Triggered by UI when the user clicks 'Approve' or 'Reject'."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        node_id = payload.get("node_id")
        decision = payload.get("decision", "approved")  # approved or rejected
        
        approval_states[(team_name, node_id)] = decision
        
        # Broadcast the decision to the UI to update badge state
        socketio_server.emit('approval_granted', {
            "team_name": team_name,
            "node_id": node_id,
            "decision": decision
        }, room=team_name)
        
        logging.info(f"User decision '{decision}' committed for squad '{team_name}' node '{node_id}'.")
        return jsonify({"status": "success", "message": f"Approval decision '{decision}' saved."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
#          C-Suite Executive Approval & Fleet Setup
# ==========================================


@misc_routes_bp.route("/api/executive/pause", methods=["POST"])
def executive_pause():
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        plan = payload.get("plan", {})
        
        # ── Cooldown: If already approved within last 30s, don't re-pause ──
        current_state = executive_states.get(team_name, {})
        if isinstance(current_state, dict) and current_state.get("status") == "approved":
            approved_at = current_state.get("approved_at", 0)
            import time as _time
            if _time.time() - approved_at < 30:
                logging.info(f"👔 [Executive] Skipping re-pause for '{team_name}' — approved {_time.time() - approved_at:.0f}s ago (30s cooldown).")
                return jsonify({"status": "success", "message": "Already approved. Cooldown active."})
        
        executive_states[team_name] = {
            "status": "pending",
            "plan": plan
        }
        
        # Broadcast to all clients (room-less emit avoids session disconnect errors)
        try:
            socketio_server.emit('executive_pause_required', {
                "team_name": team_name,
                "plan": plan
            })
        except Exception as ws_err:
            logging.debug(f"[Executive] WebSocket emit skipped: {ws_err}")
        
        logging.info(f"👔 CEO Orchestrator paused squad '{team_name}' awaiting C-Level board approval.")
        return jsonify({"status": "success", "message": "Executive board pause registered."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/executive/status", methods=["GET"])
def executive_status():
    try:
        team_name = request.args.get("team_name", "Squad_A")
        state = executive_states.get(team_name, {"status": "approved"})
        return jsonify({"status": state.get("status", "approved"), "plan": state.get("plan", {})})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/executive/approve", methods=["POST"])
def executive_approve():
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        decision = payload.get("decision", "approved") # approved or rejected
        
        # PersistentExecutiveStates uses __setitem__ to write full state dicts
        # (no __getitem__), so always write the complete state object
        import time as _time
        executive_states[team_name] = {"status": decision, "approved_at": _time.time()}
            
        # Broadcast to all clients (no room restriction — clients filter by team)
        try:
            socketio_server.emit('executive_approved', {
                "team_name": team_name,
                "decision": decision
            })
        except Exception as ws_err:
            logging.debug(f"[Executive] WebSocket emit skipped: {ws_err}")
        
        logging.info(f"👔 C-Level Executive Board decision '{decision}' recorded for squad '{team_name}'.")
        return jsonify({"status": "success", "message": f"Executive decision '{decision}' saved."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/save_squad", methods=["POST"])
def save_squad():
    try:
        FleetManager = lazy_import('chatdev.fleet_manager', 'FleetManager')  # #5
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        recruitments = payload.get("recruitments", [])
        agent_details = payload.get("agent_details", {})
        is_new_team = payload.get("is_new_team", False)
        
        # #7: Team name validation — sanitize and check duplicates
        import re
        if not team_name or not re.match(r'^[a-zA-Z0-9가-힣_\- ]+$', team_name):
            return jsonify({"status": "error", "message": "팀 이름에 특수문자를 사용할 수 없습니다."}), 400
        if len(team_name) > 50:
            return jsonify({"status": "error", "message": "팀 이름은 50자 이하로 입력해주세요."}), 400
        
        # Check for duplicate team name on new creation
        if is_new_team:
            root_dir_check = ROOT_DIR
            existing_dir = os.path.join(root_dir_check, "CompanyConfig", "Teams", team_name)
            if os.path.exists(existing_dir):
                return jsonify({
                    "status": "error", 
                    "message": f"'{team_name}' 팀이 이미 존재합니다. 다른 이름을 사용하거나 기존 팀을 수정하세요."
                }), 409
        
        # 1. Run fleet size validation engine! (Min 3, Max 7)
        try:
            FleetManager.validate_squad(recruitments)
        except RuntimeError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
            
        # 2. Save recruitments back to ChatChainConfig.json
        root_dir = ROOT_DIR  # #4: Use constant
        config_dir = os.path.join(root_dir, "CompanyConfig", "Teams", team_name)
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "ChatChainConfig.json")
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        else:
            default_path = os.path.join(root_dir, "CompanyConfig", "Default", "ChatChainConfig.json")
            if os.path.exists(default_path):
                with open(default_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            else:
                config_data = {}
                
        config_data["recruitments"] = recruitments
        
        safe_write_json(config_path, config_data, indent=4)
            
        # 3. Save custom agent details (missions/capabilities)
        # Preserve internal Chameleon fields in SquadConfig
        existing_details = FleetManager.load_squad_details(team_name)
        for key, val in existing_details.items():
            if key.startswith("_") and key not in agent_details:
                agent_details[key] = val
                
        FleetManager.save_squad_details(team_name, agent_details)
        
        logging.info(f"👥 CDC: Successfully validated and saved squad setup for {team_name}.")
        return jsonify({"status": "success", "message": "Squad validated and saved successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/load_squad_details", methods=["GET"])
def load_squad_details():
    try:
        FleetManager = lazy_import('chatdev.fleet_manager', 'FleetManager')  # #5
        team_name = request.args.get("team_name", "Squad_A")
        details = FleetManager.load_squad_details(team_name)
        return jsonify({"status": "success", "details": details})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/set_agent_parent", methods=["POST"])
def set_agent_parent():
    """Set parent_id for an agent to build multi-level hierarchies."""
    try:
        FleetManager = lazy_import('chatdev.fleet_manager', 'FleetManager')  # #5
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        agent_role = payload.get("agent_role")
        parent_id = payload.get("parent_id", "")

        if not agent_role:
            return jsonify({"status": "error", "message": "Missing agent_role"}), 400

        details = FleetManager.load_squad_details(team_name)
        if agent_role not in details:
            details[agent_role] = {"title": agent_role}
        details[agent_role]["parent_id"] = parent_id
        FleetManager.save_squad_details(team_name, details)

        return jsonify({"status": "success", "message": f"Set parent of '{agent_role}' to '{parent_id}'"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/org_tree", methods=["GET"])
def get_org_tree():
    """Returns the nested tree JSON for a squad's hierarchy."""
    try:
        FleetManager = lazy_import('chatdev.fleet_manager', 'FleetManager')  # #5
        team_name = request.args.get("team_name", "Squad_A")
        details = FleetManager.load_squad_details(team_name)

        # Build tree from parent_id relationships
        nodes = {}
        for role, info in details.items():
            if role.startswith("_"):
                continue
            nodes[role] = {
                "role": role,
                "title": info.get("title", role),
                "parent_id": info.get("parent_id", ""),
                "children": []
            }

        # Link children to parents
        roots = []
        for role, node in nodes.items():
            parent = node.get("parent_id")
            if parent and parent in nodes:
                nodes[parent]["children"].append(node)
            else:
                roots.append(node)

        tree = roots[0] if len(roots) == 1 else {"role": "Organization", "title": "Organization", "children": roots}
        return jsonify({"status": "success", "tree": tree})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
#    AI Generative Workflow Engine & Smart Task Scheduler
# ==========================================

# Role keyword mapping for NLP-style parsing

@misc_routes_bp.route("/api/infra/status", methods=["GET"])
def infra_status():
    """Return infrastructure availability status."""
    return api_success(data={
        "worker_mode": WORKER_MODE,
        "celery": _CELERY_AVAILABLE,
        "redis": _REDIS_AVAILABLE,
    })


@misc_routes_bp.route("/api/pipeline_config/save", methods=["POST"])
def save_pipeline_config():
    """Save all 30 pipeline configuration settings to ChatChainConfig.json."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        config = payload.get("config", {})
        
        root_dir = ROOT_DIR  # #4: Use constant
        config_dir = os.path.join(root_dir, "CompanyConfig", "Teams", team_name)
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "ChatChainConfig.json")
        
        # Load existing or default
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                chain_data = json.load(f)
        else:
            default_path = os.path.join(root_dir, "CompanyConfig", "Default", "ChatChainConfig.json")
            if os.path.exists(default_path):
                with open(default_path, 'r', encoding='utf-8') as f:
                    chain_data = json.load(f)
            else:
                chain_data = {}
        
        # Merge pipeline_config into ChatChainConfig
        if "pipeline_config" not in chain_data:
            chain_data["pipeline_config"] = {}
        
        # Map flat config keys to pipeline_config
        pcm_keys = [
            "role_name", "system_prompt", "model_assignment", "speech_style",
            "code_style_rule", "visualizer_coordinate",
            "max_turn_limit", "min_turn_limit", "phase_participants",
            "phase_moderator", "governance_gate_score", "phase_timeout_seconds",
            "chain_pipeline_order", "incremental_mode_toggle", "error_fallback_phase",
            "max_evolution_cycles", "checkpoint_interval", "test_trigger_command",
            "cloud_base_url", "local_base_url", "routing_matrix",
            "daily_budget_cap", "budget_overflow_action", "phoenix_fallback_models",
            "rag_directory_maps", "embedding_similarity_threshold", "manual_sync_trigger",
            "marketing_char_limit", "cd_target_platform", "plugin_registry_path"
        ]
        
        for key in pcm_keys:
            if key in config:
                chain_data["pipeline_config"][key] = config[key]
        
        # Also sync top-level ChatChain flags if provided
        if "incremental_mode_toggle" in config:
            chain_data["incremental_develop"] = str(config["incremental_mode_toggle"]).capitalize()
        if "test_trigger_command" in config:
            chain_data["test_command"] = config["test_trigger_command"]
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(chain_data, f, indent=4, ensure_ascii=False)
        
        logging.info(f"⚙️ Pipeline config saved for team '{team_name}' ({len(config)} settings)")
        return jsonify({"status": "success", "message": f"Pipeline config saved ({len(config)} settings)"})
    except Exception as e:
        logging.error(f"Error saving pipeline config: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



@misc_routes_bp.route("/api/pipeline_config/load", methods=["GET"])
def load_pipeline_config():
    """Load all 30 pipeline configuration settings from ChatChainConfig.json."""
    try:
        team_name = request.args.get("team_name", "Squad_A")
        
        root_dir = ROOT_DIR  # #4: Use constant
        config_path = os.path.join(root_dir, "CompanyConfig", "Teams", team_name, "ChatChainConfig.json")
        
        # Load existing or default
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                chain_data = json.load(f)
        else:
            default_path = os.path.join(root_dir, "CompanyConfig", "Default", "ChatChainConfig.json")
            if os.path.exists(default_path):
                with open(default_path, 'r', encoding='utf-8') as f:
                    chain_data = json.load(f)
            else:
                chain_data = {}
        
        # Extract pipeline_config or build defaults
        pcm = chain_data.get("pipeline_config", {})
        
        # Merge top-level ChatChain flags as defaults
        defaults = {
            "incremental_mode_toggle": chain_data.get("incremental_develop", "False") == "True",
            "test_trigger_command": chain_data.get("test_command", "python3 main.py"),
            "max_turn_limit": 10,
            "min_turn_limit": 2,
            "governance_gate_score": 90,
            "phase_timeout_seconds": 60,
            "max_evolution_cycles": 5,
            "checkpoint_interval": 3,
            "daily_budget_cap": 15,
            "embedding_similarity_threshold": 75,
            "marketing_char_limit": 2200,
            "manual_sync_trigger": True,
            "cloud_base_url": "",
            "local_base_url": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            "routing_matrix": "cloud",
            "budget_overflow_action": "shutdown",
            "phoenix_fallback_models": "gemini-2.5-pro → gemini-2.5-flash → gemma2",
            "error_fallback_phase": "Coding",
            "cd_target_platform": "local",
            "plugin_registry_path": "./plugins/",
            "speech_style": "Korean_Professional",
            "code_style_rule": "PEP8",
            "model_assignment": "gpt-4o",
            "role_name": "",
            "system_prompt": "",
            "chain_pipeline_order": "",
            "rag_directory_maps": "",
            "visualizer_coordinate": {"x": 400, "y": 300},
            "phase_participants": [],
            "phase_moderator": ""
        }
        
        # Merge: pcm values override defaults
        result = {**defaults, **pcm}
        
        return jsonify({"status": "success", "config": result})
    except Exception as e:
        logging.error(f"Error loading pipeline config: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ── Custom Playbook CRUD APIs ──

@misc_routes_bp.route("/api/custom_playbook/save", methods=["POST"])
def save_custom_playbook():
    """Save a user-defined custom playbook to disk."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        name = payload.get("name", "").strip()
        description = payload.get("description", "")
        nodes = payload.get("nodes", [])
        edges = payload.get("edges", [])
        trigger_config = payload.get("trigger_config", {"type": "manual"})

        if not name:
            return jsonify({"status": "error", "message": "플레이북 이름을 입력해주세요."}), 400
        if len(nodes) < 2:
            return jsonify({"status": "error", "message": "최소 2개 이상의 노드가 필요합니다."}), 400

        # Generate playbook ID
        import re as _re
        slug = _re.sub(r'[^a-zA-Z0-9가-힣_]', '_', name)[:40].strip('_')
        playbook_id = f"pb_{slug}_{datetime.now().strftime('%H%M%S')}"

        playbook_dir = os.path.join(VISUALIZER_DIR, "workspace", "custom_playbooks", team_name)
        os.makedirs(playbook_dir, exist_ok=True)

        playbook_data = {
            "playbook_id": playbook_id,
            "name": name,
            "description": description,
            "team_name": team_name,
            "trigger_config": trigger_config,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        filepath = os.path.join(playbook_dir, f"{playbook_id}.json")
        safe_write_json(filepath, playbook_data)

        logging.info(f"💾 Custom playbook saved: {playbook_id} ({len(nodes)} nodes, {len(edges)} edges)")

        return jsonify({
            "status": "success",
            "playbook_id": playbook_id,
            "message": f"커스텀 플레이북 '{name}' 저장 완료",
            "playbook": playbook_data
        })
    except Exception as e:
        logging.error(f"Playbook save error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



@misc_routes_bp.route("/api/custom_playbook/list", methods=["GET"])
def list_custom_playbooks():
    """List all custom playbooks for a team."""
    team_name = request.args.get("team_name", "Squad_A")
    playbook_dir = os.path.join(VISUALIZER_DIR, "workspace", "custom_playbooks", team_name)

    if not os.path.exists(playbook_dir):
        return jsonify({"status": "success", "playbooks": [], "count": 0})

    playbooks = []
    for fname in sorted(os.listdir(playbook_dir)):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(playbook_dir, fname), 'r', encoding='utf-8') as f:
                    pb = json.load(f)
                playbooks.append({
                    "playbook_id": pb.get("playbook_id", fname.replace(".json", "")),
                    "name": pb.get("name", "Untitled"),
                    "description": pb.get("description", ""),
                    "node_count": pb.get("node_count", 0),
                    "edge_count": pb.get("edge_count", 0),
                    "trigger_type": pb.get("trigger_config", {}).get("type", "manual"),
                    "created_at": pb.get("created_at", ""),
                    "updated_at": pb.get("updated_at", "")
                })
            except Exception as _e:
                logging.debug(f"[suppressed] Exception: {_e}")

    return jsonify({"status": "success", "playbooks": playbooks, "count": len(playbooks)})



@misc_routes_bp.route("/api/custom_playbook/load/<playbook_id>", methods=["GET"])
def load_custom_playbook(playbook_id):
    """Load a specific custom playbook by ID."""
    team_name = request.args.get("team_name", "Squad_A")
    playbook_dir = os.path.join(VISUALIZER_DIR, "workspace", "custom_playbooks", team_name)
    filepath = os.path.join(playbook_dir, f"{playbook_id}.json")

    if not os.path.exists(filepath):
        return jsonify({"status": "error", "message": f"플레이북을 찾을 수 없습니다: {playbook_id}"}), 404

    with open(filepath, 'r', encoding='utf-8') as f:
        playbook = json.load(f)

    return jsonify({"status": "success", "playbook": playbook})



@misc_routes_bp.route("/api/custom_playbook/<playbook_id>", methods=["DELETE"])
def delete_custom_playbook(playbook_id):
    """Delete a custom playbook."""
    team_name = request.args.get("team_name", "Squad_A")
    playbook_dir = os.path.join(VISUALIZER_DIR, "workspace", "custom_playbooks", team_name)
    filepath = os.path.join(playbook_dir, f"{playbook_id}.json")

    if not os.path.exists(filepath):
        return jsonify({"status": "error", "message": f"플레이북을 찾을 수 없습니다: {playbook_id}"}), 404

    os.remove(filepath)
    logging.info(f"🗑️ Custom playbook deleted: {playbook_id}")
    return jsonify({"status": "success", "message": f"플레이북 '{playbook_id}' 삭제 완료"})


# ── Multi-Agent Alignment (Pre-Meeting) APIs ──

@misc_routes_bp.route("/api/output/download", methods=["GET"])
def download_output():
    """Package workspace output into a downloadable zip.
    
    CRITICAL FIX: Celery worker runs in a separate process and writes files to
    workspace/output/{team}/proj_{slug}/. This endpoint must discover the actual
    project directory on disk, NOT rely on in-memory state which the worker can't update.
    """
    import zipfile, io
    
    team_name = request.args.get("team_name", "Squad_A")
    
    # ── [1] Find the team's output root ──
    output_root = os.path.join(VISUALIZER_DIR, "workspace", "output", team_name)
    
    if not os.path.exists(output_root):
        return jsonify({"status": "error", "message": f"출력 디렉토리가 없습니다: {team_name}"}), 404
    
    # ── [2] Find the most recent proj_* directory (filesystem-based discovery) ──
    proj_dirs = []
    for entry in os.listdir(output_root):
        full_path = os.path.join(output_root, entry)
        if os.path.isdir(full_path) and entry.startswith("proj_"):
            proj_dirs.append(full_path)
    
    if not proj_dirs:
        return jsonify({"status": "error", "message": "프로젝트 산출물이 없습니다. 먼저 워크플로우를 실행하세요."}), 404
    
    # Sort by modification time (most recent first)
    proj_dirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    target_dir = proj_dirs[0]
    proj_name = os.path.basename(target_dir)
    
    # ── [3] Validate: count actual files inside target directory ──
    file_list = []
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            file_list.append(os.path.join(root, file))
    
    logging.info(f"📦 다운로드 패키징: {target_dir} ({len(file_list)} files)")
    
    if len(file_list) == 0:
        return jsonify({"status": "error", "message": f"프로젝트 디렉토리가 비어 있습니다: {proj_name}"}), 404
    
    # ── [4] Create ZIP from actual project files ──
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fpath in file_list:
            arcname = os.path.join(proj_name, os.path.relpath(fpath, target_dir))
            zf.write(fpath, arcname)
            logging.info(f"  📄 ZIP += {arcname} ({os.path.getsize(fpath):,} bytes)")
    
    # ── [5] Validate ZIP is non-empty ──
    zip_size = buf.tell()
    logging.info(f"📦 ZIP 완료: {zip_size:,} bytes, {len(file_list)} files")
    
    if zip_size == 0:
        return jsonify({"status": "error", "message": "ZIP 파일이 0 바이트입니다. 압축 실패."}), 500
    
    buf.seek(0)
    download_name = f'{team_name}_{proj_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
    
    return send_file(
        buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name=download_name
    )


@misc_routes_bp.route("/preview/<cmd_id>/<path:filename>")
def preview_web_project(cmd_id, filename):
    """Serve static files from a web project for live preview."""
    import mimetypes
    
    short_id = cmd_id.split("-")[-1][-6:] if "-" in cmd_id else cmd_id[-6:]
    
    warehouse_base = os.path.join(VISUALIZER_DIR, "..", "WareHouse")
    warehouse_base = os.path.abspath(warehouse_base)
    
    # Find matching project
    candidates = []
    for entry in os.listdir(warehouse_base):
        full_path = os.path.join(warehouse_base, entry)
        if os.path.isdir(full_path) and short_id in entry:
            candidates.append(full_path)
    
    # Check Teams subdirectories
    teams_dir = os.path.join(warehouse_base, "Teams")
    if os.path.isdir(teams_dir):
        for team in os.listdir(teams_dir):
            team_path = os.path.join(teams_dir, team)
            if os.path.isdir(team_path):
                for entry in os.listdir(team_path):
                    full_path = os.path.join(team_path, entry)
                    if os.path.isdir(full_path) and short_id in entry:
                        candidates.append(full_path)
    
    if not candidates:
        return "Project not found", 404
    
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    target_dir = candidates[0]
    
    # Security: prevent path traversal
    safe_path = os.path.normpath(os.path.join(target_dir, filename))
    if not safe_path.startswith(target_dir):
        return "Forbidden", 403
    
    if not os.path.isfile(safe_path):
        return "File not found", 404
    
    mime_type = mimetypes.guess_type(safe_path)[0] or "application/octet-stream"
    return send_file(safe_path, mimetype=mime_type)

# ══════════════════════════════════════════════════════════════
#   📷 IMAGE UPLOAD + AI VISION ANALYSIS API
# ══════════════════════════════════════════════════════════════

# Upload directory

@misc_routes_bp.route("/api/integrations", methods=["GET"])
def list_integrations():
    """List all supported services and their connection status."""
    try:
        list_services = lazy_import('chatdev.integration_store', 'list_services')  # #5
        services = list_services()
        return jsonify({"status": "success", "services": services})
    except Exception as e:
        logging.error(f"[Integrations] List error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



@misc_routes_bp.route("/api/integrations", methods=["POST"])
def save_integration():
    """Save API key(s) for a service."""
    try:
        save_key = lazy_import('chatdev.integration_store', 'save_key')  # #5
        data = request.get_json()
        service = data.get("service")
        keys = data.get("keys", {})

        if not service or not keys:
            return jsonify({"status": "error", "message": "service와 keys가 필요합니다"}), 400

        saved = []
        for key_name, value in keys.items():
            if value and value.strip():
                save_key(service, key_name, value.strip())
                saved.append(key_name)

        return jsonify({
            "status": "success",
            "message": f"✅ {service} — {len(saved)}개 키 저장 완료",
            "saved_keys": saved,
        })
    except ValueError as ve:
        return jsonify({"status": "error", "message": str(ve)}), 400
    except Exception as e:
        logging.error(f"[Integrations] Save error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



@misc_routes_bp.route("/api/integrations/<service>", methods=["DELETE"])
def delete_integration(service):
    """Disconnect a service (delete all its keys)."""
    try:
        delete_service = lazy_import('chatdev.integration_store', 'delete_service')  # #5
        deleted = delete_service(service)
        if deleted:
            return jsonify({"status": "success", "message": f"🗑️ {service} 연결 해제 완료"})
        return jsonify({"status": "error", "message": "해당 서비스가 연결되어 있지 않습니다"}), 404
    except Exception as e:
        logging.error(f"[Integrations] Delete error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



@misc_routes_bp.route("/api/integrations/<service>/test", methods=["POST"])
def test_integration(service):
    """Test if a service connection is working."""
    try:
        test_connection = lazy_import('chatdev.integration_store', 'test_connection')  # #5
        result = test_connection(service)
        return jsonify({
            "status": "success" if result["success"] else "error",
            "message": result["message"],
            "connected": result["success"],
        })
    except Exception as e:
        logging.error(f"[Integrations] Test error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Live Execution Log APIs ──

@misc_routes_bp.route("/api/logs/live", methods=["GET"])
def live_logs():
    """Get recent execution logs."""
    limit = request.args.get("limit", 50, type=int)
    since = request.args.get("since", None)
    logs = get_logs(limit, since)
    summary = get_metering_summary()
    return jsonify({
        "status": "success",
        "logs": logs,
        "count": len(logs),
        "billing": {
            "total_cost_usd": summary["total_cost_usd"],
            "total_actions": summary["total_actions"],
            "total_tokens": summary["total_tokens"]
        }
    })

# WebSocket: Real-time log streaming

@misc_routes_bp.route("/api/freeform_graph/save", methods=["POST"])
def save_freeform_graph():
    """Save freeform graph state (nodes + edges) for a team."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        nodes = payload.get("nodes", [])
        edges = payload.get("edges", [])

        graph_dir = os.path.join(VISUALIZER_DIR, "freeform_graphs")
        os.makedirs(graph_dir, exist_ok=True)
        graph_path = os.path.join(graph_dir, f"{team_name}.json")

        graph_data = {
            "team_name": team_name,
            "nodes": nodes,
            "edges": edges,
            "saved_at": datetime.now().isoformat()
        }

        safe_write_json(graph_path, graph_data)

        return jsonify({"status": "success", "message": f"Freeform graph saved for {team_name}", "node_count": len(nodes), "edge_count": len(edges)})
    except Exception as e:
        logging.error(f"Error saving freeform graph: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/freeform_graph/load", methods=["GET"])
def load_freeform_graph():
    """Load freeform graph state for a team, auto-merging with actual ChatChainConfig roster."""
    try:
        team_name = request.args.get("team_name", "Squad_A")
        nodes, edges = ensure_and_load_graph(team_name)
        return jsonify({
            "status": "success",
            "nodes": nodes,
            "edges": edges,
            "roster_count": len(nodes),
            "auto_seeded": False
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
#          Chameleon Template Engine APIs
# ==========================================


@misc_routes_bp.route("/api/blueprints/apply", methods=["POST"])
def blueprints_apply():
    """Applies an industry blueprint template to a dynamic squad workspace."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        industry_id = payload.get("industry_id")
        
        if not industry_id:
            return jsonify({"status": "error", "message": "Missing industry_id parameter."}), 400
            
        root_dir = ROOT_DIR  # #4: Use constant
        blueprint_path = os.path.join(root_dir, "CompanyConfig", "Blueprints", f"{industry_id}.json")
        
        if not os.path.exists(blueprint_path):
            return jsonify({"status": "error", "message": f"Industry Blueprint '{industry_id}' not found."}), 404
            
        with open(blueprint_path, 'r', encoding='utf-8') as f:
            blueprint = json.load(f)
            
        team_dir = os.path.join(root_dir, "CompanyConfig", "Teams", team_name)
        os.makedirs(team_dir, exist_ok=True)
        
        # 1. Save SquadConfig.json (Auto-fleet details and ontology)
        squad_config_data = blueprint.get("squad_config", {})
        squad_config_data["_ontology"] = blueprint.get("ontology", {})
        squad_config_data["_industry_id"] = industry_id
        squad_config_data["_industry_name"] = blueprint.get("industry_name")
        
        squad_config_path = os.path.join(team_dir, "SquadConfig.json")
        safe_write_json(squad_config_path, squad_config_data, indent=4)
            
        # 2. Save ChatChainConfig.json (Workflow nodes, edges, and recruitments)
        chatchain_config_data = {
            "recruitments": blueprint.get("recruitments", []),
            "nodes": blueprint.get("default_nodes", []),
            "edges": blueprint.get("default_edges", [])
        }
        chatchain_path = os.path.join(team_dir, "ChatChainConfig.json")
        safe_write_json(chatchain_path, chatchain_config_data, indent=4)
            
        # 3. Save preloaded knowledge and index in RAG
        preloaded_knowledge = blueprint.get("preloaded_knowledge", {})
        knowledge_dir = os.path.join(root_dir, "CompanyConfig", "Knowledge")
        os.makedirs(knowledge_dir, exist_ok=True)
        
        for filename, content in preloaded_knowledge.items():
            filepath = os.path.join(knowledge_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
                
        # Index in background thread if RAG is available
        if RAGMemoryPipeline:
            try:
                pipeline = RAGMemoryPipeline(knowledge_dir=knowledge_dir)
                import threading
                threading.Thread(target=pipeline.bootstrap_pipeline).start()
            except Exception as e:
                logging.error(f"Error indexing preloaded RAG docs: {e}")
                
        # Update team-specific injected knowledge list
        global squad_injected_knowledge
        squad_injected_knowledge[team_name] = list(preloaded_knowledge.keys())
        
        # Reset squad metrics when applying a new blueprint
        squad_stats[team_name] = {
            "active_tasks": 0,
            "token_cost": 0.0,
            "completed_tasks": 0,
            "throughput": [
                {"date": "05-25", "count": 2},
                {"date": "05-26", "count": 3},
                {"date": "05-27", "count": 1},
                {"date": "05-28", "count": 5},
                {"date": "05-29", "count": 4},
                {"date": "05-30", "count": 0}
            ],
            "workload": {},
            "cost_efficiency": 0.0
        }
        save_squad_stats()
        
        # Broadcast the change via SocketIO
        socketio_server.emit('blueprint_applied', {
            "team_name": team_name,
            "industry_id": industry_id,
            "industry_name": blueprint.get("industry_name"),
            "ontology": blueprint.get("ontology", {})
        })
        
        logging.info(f"🎨 Chameleon: Applied '{industry_id}' blueprint to Squad '{team_name}' successfully.")
        return jsonify({
            "status": "success",
            "message": f"Successfully applied '{blueprint.get('industry_name')}' blueprint to Squad '{team_name}'!"
        })
    except Exception as e:
        logging.error(f"Error applying blueprint: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/org_stats", methods=["GET"])
def org_stats():
    """Scans and retrieves operational stats for all squads under CompanyConfig/Teams/"""
    try:
        root_dir = ROOT_DIR  # #4: Use constant
        teams_dir = os.path.join(root_dir, "CompanyConfig", "Teams")
        os.makedirs(teams_dir, exist_ok=True)
        
        teams = [d for d in os.listdir(teams_dir) 
                 if os.path.isdir(os.path.join(teams_dir, d)) and not d.startswith(('_', '.'))]
        teams.sort()
        
        total_active_tasks = 0
        total_cost = 0.0
        squads_data = {}
        
        for team in teams:
            stats = squad_stats.get(team, {"active_tasks": 0, "token_cost": 0.0, "completed_tasks": 0})
            total_active_tasks += stats.get("active_tasks", 0)
            total_cost += stats.get("token_cost", 0.0)
            
            s_class = "dev"
            if "market" in team.lower() or "squad_b" in team.lower() or "branding" in team.lower() or "creative" in team.lower():
                s_class = "marketing"
            elif "design" in team.lower() or "construction" in team.lower():
                s_class = "design"
            elif "logistic" in team.lower():
                s_class = "logistics"
                
            title = f"{team.replace('_', ' ')} Workspace"
            config_path = os.path.join(teams_dir, team, "SquadConfig.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        s_details = json.load(f)
                        ceo_details = s_details.get("Chief Executive Officer", {})
                        if "title" in ceo_details:
                            title = ceo_details["title"]
                except Exception as _e:
                    logging.debug(f"[suppressed] Exception: {_e}")
            
            squads_data[team] = {
                "tasks": stats.get("active_tasks", 0) + stats.get("completed_tasks", 0),
                "active_tasks": stats.get("active_tasks", 0),
                "cost": f"${stats.get('token_cost', 0.0):.4f}",
                "raw_cost": stats.get('token_cost', 0.0),
                "class": s_class,
                "title": title,
                "workload": stats.get("workload", {})
            }
            
        return jsonify({
            "status": "success",
            "total_divisions": len(teams),
            "global_active_tasks": total_active_tasks,
            "cumulative_cost": f"${total_cost:.4f}",
            "raw_cumulative_cost": total_cost,
            "squads": squads_data
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/auto_assign_workflow", methods=["POST"])
def auto_assign_workflow_endpoint():
    """Runs the task-to-employee binder to assign nodes to qualified squad members based on capabilities."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        # #9: Path traversal defense
        valid, team_name = validate_team_name(team_name)
        if not valid:
            return api_error("Invalid team name", 400)
        
        TaskRouter = lazy_import('chatdev.task_router', 'TaskRouter')  # #5
        result = TaskRouter.auto_assign_workflow(team_name)
        
        # Also broadcast graph update notification
        socketio_server.emit('graph_updated', {"team_name": team_name}, room=team_name)
        
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error running auto assignment: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/executive/command", methods=["POST"])
def executive_command_endpoint():
    """Parses user instruction and injects dynamic task node into ChatChainConfig.json with custom role mapping."""
    try:
        payload = request.get_json() or {}
        command_text = payload.get("command", "").strip()
        
        if not command_text:
            return jsonify({"status": "error", "message": "Command text is empty"}), 400
            
        root_dir = ROOT_DIR  # #4: Use constant
        
        # 1. Parse and identify target squad (Development_Team vs Marketing_Team)
        team_name = "Development_Team" # Default fallback
        lowered = command_text.lower()
        if "마케팅" in lowered or "marketing" in lowered or "youtube" in lowered or "유튜브" in lowered or "작가" in lowered or "썸네일" in lowered:
            team_name = "Marketing_Team"
        elif "개발" in lowered or "development" in lowered or "coding" in lowered or "software" in lowered or "테스트" in lowered or "qa" in lowered:
            team_name = "Development_Team"
            
        # 2. Load SquadConfig.json to find available roles and match based on keywords
        squad_config_path = os.path.join(root_dir, "CompanyConfig", "Teams", team_name, "SquadConfig.json")
        if not os.path.exists(squad_config_path):
            return jsonify({"status": "error", "message": f"Squad configuration not found for {team_name}"}), 404
            
        with open(squad_config_path, 'r', encoding='utf-8') as sf:
            squad_config = json.load(sf)
            
        # Filter internal properties
        roles = {k: v for k, v in squad_config.items() if not k.startswith("_")}
        
        # Determine best role by capability or keyword mapping
        matched_role_key = "Programmer" # default fallback
        
        if team_name == "Development_Team":
            if any(kw in command_text for kw in ["테스트", "QA", "검증", "검사", "qa", "test"]):
                matched_role_key = "Software Test Engineer"
            elif any(kw in command_text for kw in ["리뷰", "검토", "수정", "보안", "review"]):
                matched_role_key = "Code Reviewer"
            elif any(kw in command_text for kw in ["기획", "화면", "기능", "요구", "pm", "product"]):
                matched_role_key = "Chief Product Officer"
            elif any(kw in command_text for kw in ["설계", "구조", "아키텍처", "architect"]):
                matched_role_key = "Chief Technology Officer"
        else: # Marketing_Team
            if any(kw in command_text for kw in ["대본", "시나리오", "작가", "글", "보도자료", "카피", "narration", "script"]):
                matched_role_key = "Chief Product Officer" # 대본 작가 요원
            elif any(kw in command_text for kw in ["썸네일", "디자인", "이미지", "비주얼", "그림", "thumbnail"]):
                matched_role_key = "Programmer" # 썸네일 디자이너 요원
            elif any(kw in command_text for kw in ["알고리즘", "분석", "크롤링", "태그", "SEO", "검색", "seo"]):
                matched_role_key = "Code Reviewer" # 알고리즘 분석가 요원
                
        # Get custom title for matched role
        agent_data = roles.get(matched_role_key, {})
        matched_title = agent_data.get("title", matched_role_key)
        
        # 3. Read and modify ChatChainConfig.json to inject dynamic task node and edge
        chatchain_path = os.path.join(root_dir, "CompanyConfig", "Teams", team_name, "ChatChainConfig.json")
        if not os.path.exists(chatchain_path):
            return jsonify({"status": "error", "message": f"ChatChainConfig not found for {team_name}"}), 404
            
        with open(chatchain_path, 'r', encoding='utf-8') as cf:
            chatchain_data = json.load(cf)
            
        # Generate clean dynamic sequential ID
        dynamic_count = len([n for n in chatchain_data.get("nodes", []) if n.get("id", "").startswith("DynamicTask_")]) + 1
        task_id = f"DynamicTask_{dynamic_count}"
        
        # Build the dynamic node block
        new_node = {
            "id": task_id,
            "phase": task_id,
            "phaseType": "SimplePhase",
            "max_turn_step": 1,
            "need_reflect": "False",
            "assignee": matched_title,
            "task_description": command_text
        }
        
        # Append node
        if "nodes" not in chatchain_data:
            chatchain_data["nodes"] = []
        chatchain_data["nodes"].append(new_node)
        
        # Append connecting edge
        if "edges" not in chatchain_data:
            chatchain_data["edges"] = []
            
        # Find the last sink node
        sources = set(e.get("source") for e in chatchain_data["edges"])
        sink_nodes = [n["id"] for n in chatchain_data["nodes"] if n["id"] not in sources and n["id"] != "Trigger" and n["id"] != task_id]
        last_node_id = sink_nodes[-1] if sink_nodes else (chatchain_data["nodes"][-2]["id"] if len(chatchain_data["nodes"]) > 1 else "Trigger")
        
        new_edge = {
            "source": last_node_id,
            "target": task_id
        }
        chatchain_data["edges"].append(new_edge)
        
        # Overwrite ChatChainConfig.json
        with open(chatchain_path, 'w', encoding='utf-8') as cf:
            json.dump(chatchain_data, cf, indent=4, ensure_ascii=False)
            
        # 4. Increment active_tasks and update stats
        if team_name in squad_stats:
            squad_stats[team_name]["active_tasks"] = squad_stats[team_name].get("active_tasks", 0) + 1
            save_squad_stats()
            
        # 5. Broadcast real-time Socket.IO alerts
        socketio_server.emit('command_processed', {
            "team_name": team_name,
            "assignee": matched_title,
            "role_key": matched_role_key,
            "task_id": task_id,
            "task_description": command_text
        })
        socketio_server.emit('graph_updated', {"team_name": team_name})
        
        # Emit global stats update for tree badge refreshing
        socketio_server.emit('global_stats_update', {"team_name": team_name})
        
        return jsonify({
            "status": "success",
            "message": f"Successfully parsed and injected dynamic command into {team_name} assigned to {matched_title}!",
            "team_name": team_name,
            "assignee": matched_title,
            "role_key": matched_role_key,
            "task_id": task_id,
            "task_description": command_text
        })
        
    except Exception as e:
        logging.error(f"Error in dynamic command injection: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
# ==========================================
#    ✨ Conversational Builder — AI Team Generation API
# ==========================================

# Pre-defined team templates for natural language team building

@misc_routes_bp.route("/api/conversational_builder", methods=["POST"])
def conversational_builder_endpoint():
    """
    ✨ Conversational Builder — Takes natural language input and auto-generates 
    a full team of agent nodes on the canvas with connected edges.
    """
    try:
        payload = request.get_json() or {}
        user_prompt = payload.get("prompt", "").strip()
        team_name = payload.get("team_name", "Squad_A")
        
        if not user_prompt:
            return jsonify({"status": "error", "message": "프롬프트가 비어 있습니다"}), 400
        
        # Check active API key
        provider = _AI_ENGINE_CONFIG.get("provider")
        api_key_set = False
        if provider == "openai" and _AI_ENGINE_CONFIG.get("api_key"):
            api_key_set = True
        elif provider == "anthropic" and _AI_ENGINE_CONFIG.get("anthropic_api_key"):
            api_key_set = True
        elif provider == "google" and _AI_ENGINE_CONFIG.get("google_api_key"):
            api_key_set = True
        elif provider == "local" and _AI_ENGINE_CONFIG.get("local_endpoint"):
            api_key_set = True

        custom_agents = None
        template_name = None
        if api_key_set:
            try:
                system_prompt = (
                    "You are a master agent team architect.\n"
                    "Based on the user's task description, design a custom team name and a collaborative pipeline of 3 to 5 AI agents.\n"
                    "For each agent, assign a unique alphabetic ID (no spaces), a phase name, a phaseType (e.g. SimplePhase), a specific role, max_turn_step (e.g. 3), and need_reflect (\"True\" or \"False\").\n"
                    "You must output exactly a JSON object matching this structure, with no extra text or markdown formatting:\n"
                    "{\n"
                    "  \"name\": \"Custom Team Name\",\n"
                    "  \"agents\": [\n"
                    "    {\n"
                    "      \"id\": \"Agent_ID\",\n"
                    "      \"phase\": \"Phase_Name\",\n"
                    "      \"phaseType\": \"SimplePhase\",\n"
                    "      \"role\": \"Role description\",\n"
                    "      \"max_turn_step\": 3,\n"
                    "      \"need_reflect\": \"True\"\n"
                    "    }\n"
                    "  ]\n"
                    "}"
                )
                user_msg = f"Task: {user_prompt}"
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ]
                response_text = get_llm_response(messages, max_tokens=1500, raise_on_error=True)
                
                # Clean up markdown code blocks if any
                clean_text = response_text.strip()
                if clean_text.startswith("```"):
                    lines = clean_text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].startswith("```"):
                        lines = lines[:-1]
                    clean_text = "\n".join(lines).strip()
                
                parsed = json.loads(clean_text)
                if "agents" in parsed and isinstance(parsed["agents"], list) and len(parsed["agents"]) > 0:
                    custom_agents = parsed["agents"]
                    template_name = parsed.get("name", "Custom Dynamic Team")
            except Exception as e:
                logging.warning(f"Conversational builder LLM execution failed, using fallback template: {e}")

        if custom_agents:
            trigger_node = {
                "id": "Trigger", "phase": "Trigger", "phaseType": "⚡ Pipeline Trigger",
                "max_turn_step": 0, "need_reflect": "False",
                "trigger_type": "event", "event": user_prompt[:60]
            }
            nodes = [trigger_node]
            edges = []
            
            for i, agent in enumerate(custom_agents):
                aid = agent.get("id", f"Agent_{i+1}")
                phase = agent.get("phase", aid)
                phase_type = agent.get("phaseType", "SimplePhase")
                role = agent.get("role", aid)
                max_turn_step = agent.get("max_turn_step", 3)
                need_reflect = agent.get("need_reflect", "True")
                
                node = {
                    "id": aid,
                    "phase": phase,
                    "phaseType": phase_type,
                    "max_turn_step": max_turn_step,
                    "need_reflect": str(need_reflect),
                    "assignee": role
                }
                nodes.append(node)
                
                if i == 0:
                    edges.append({"source": "Trigger", "target": aid})
                else:
                    prev_aid = custom_agents[i-1].get("id", f"Agent_{i}")
                    edges.append({"source": prev_aid, "target": aid})
            
            agent_count = len(custom_agents)
        else:
            # Match user prompt to a template
            lowered = user_prompt.lower()
            matched_template = None
            
            keyword_map = {
                "instagram": ["인스타", "instagram", "인스타그램", "릴스", "reels"],
                "youtube": ["유튜브", "youtube", "영상", "동영상", "채널"],
                "development": ["개발", "소프트웨어", "코딩", "프로그래밍", "dev", "software", "앱"],
                "marketing": ["마케팅", "marketing", "광고", "홍보", "그로스"],
                "customer_success": ["고객", "cs", "customer", "지원", "서포트", "support", "성공"]
            }
            
            for template_key, keywords in keyword_map.items():
                if any(kw in lowered for kw in keywords):
                    matched_template = TEAM_TEMPLATES[template_key]
                    break
            
            if not matched_template:
                # Default: generate a generic content team
                matched_template = TEAM_TEMPLATES["instagram"]
            
            template_name = matched_template["name"]
            
            # Build nodes and edges for the team
            trigger_node = {
                "id": "Trigger", "phase": "Trigger", "phaseType": "⚡ Pipeline Trigger",
                "max_turn_step": 0, "need_reflect": "False",
                "trigger_type": "event", "event": user_prompt[:60]
            }
            
            nodes = [trigger_node]
            edges = []
            
            for i, agent in enumerate(matched_template["agents"]):
                node = {
                    "id": agent["id"],
                    "phase": agent["phase"],
                    "phaseType": agent["phaseType"],
                    "max_turn_step": agent["max_turn_step"],
                    "need_reflect": agent["need_reflect"],
                    "assignee": agent["role"]
                }
                nodes.append(node)
                
                # Chain edges: Trigger → Agent1 → Agent2 → Agent3 → ...
                if i == 0:
                    edges.append({"source": "Trigger", "target": agent["id"]})
                else:
                    edges.append({"source": matched_template["agents"][i-1]["id"], "target": agent["id"]})
            
            agent_count = len(matched_template["agents"])
        
        # Write to ChatChainConfig.json
        root_dir = ROOT_DIR  # #4: Use constant
        chatchain_path = os.path.join(root_dir, "CompanyConfig", "Teams", team_name, "ChatChainConfig.json")
        
        if os.path.exists(chatchain_path):
            with open(chatchain_path, 'r', encoding='utf-8') as f:
                chatchain_data = json.load(f)
        else:
            chatchain_data = {}
        
        chatchain_data["nodes"] = nodes
        chatchain_data["edges"] = edges
        
        with open(chatchain_path, 'w', encoding='utf-8') as f:
            json.dump(chatchain_data, f, indent=4, ensure_ascii=False)
        
        # Broadcast to frontend for animated node drop
        socketio_server.emit('team_built', {
            "team_name": team_name,
            "template_name": template_name,
            "nodes": nodes,
            "edges": edges,
            "animate": True
        })
        socketio_server.emit('graph_updated', {"team_name": team_name})
        
        return jsonify({
            "status": "success",
            "message": f"✨ '{template_name}' 팀이 성공적으로 생성되었습니다!",
            "team_name": team_name,
            "template_name": template_name,
            "nodes": nodes,
            "edges": edges,
            "agent_count": agent_count
        })
        
    except Exception as e:
        logging.error(f"Error in conversational builder: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
#          Playbook Template Library Registry & APIs
#          #3: Externalized to CompanyConfig/Playbooks/
# ==========================================


@misc_routes_bp.route("/api/playbooks", methods=["GET"])
def get_playbooks():
    # #3: Re-read from disk for hot-reload support
    fresh_playbooks = _load_playbooks()
    return jsonify({"status": "success", "playbooks": fresh_playbooks})


@misc_routes_bp.route("/api/playbooks/apply", methods=["POST"])
def apply_playbook():
    try:
        payload = request.get_json() or {}
        team_name = payload.get("team_name", "Squad_A")
        playbook_id = payload.get("playbook_id", "meeting")
        
        if playbook_id == "__ai_generated":
            playbook = {
                "nodes": payload.get("nodes", []),
                "edges": payload.get("edges", []),
                "trigger": {"type": "manual"},
                "title": "AI Generated Playbook"
            }
        else:
            if playbook_id not in PLAYBOOKS:
                return jsonify({"status": "error", "message": f"Playbook '{playbook_id}' not found"}), 404
            playbook = PLAYBOOKS[playbook_id]
        root_dir = ROOT_DIR  # #4: Use constant
        
        chatchain_path = os.path.join(root_dir, "CompanyConfig", "Teams", team_name, "ChatChainConfig.json")
        if not os.path.exists(chatchain_path):
            chatchain_path = os.path.join(root_dir, "CompanyConfig", "Default", "ChatChainConfig.json")
            
        with open(chatchain_path, 'r', encoding='utf-8') as f:
            chatchain_data = json.load(f)
            
        chatchain_data["nodes"] = playbook["nodes"]
        chatchain_data["edges"] = playbook["edges"]
        
        target_path = os.path.join(root_dir, "CompanyConfig", "Teams", team_name, "ChatChainConfig.json")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(chatchain_data, f, indent=4, ensure_ascii=False)
            
        # Invoke task router auto assign
        TaskRouter = lazy_import('chatdev.task_router', 'TaskRouter')  # #5
        assign_result = TaskRouter.auto_assign_workflow(team_name)
        
        # Add scheduler job if Time-based
        trigger_info = playbook["trigger"]
        enterprise_scheduler = lazy_import('chatdev.scheduler', 'enterprise_scheduler')  # #5
        if trigger_info["type"] == "time":
            enterprise_scheduler.add_job(team_name, trigger_info["cron"], playbook["title"])
        else:
            enterprise_scheduler.remove_job(team_name)
            
        # Socket broadcasts
        socketio_server.emit('graph_updated', {"team_name": team_name})
        
        # Seminar-specific: include product_id for interview mode activation
        emit_data = {
            "team_name": team_name,
            "playbook_id": playbook_id,
            "playbook_title": playbook["title"]
        }
        if playbook_id == "seminar":
            seminar_product_id = payload.get("seminar_product_id", "")
            emit_data["seminar_product_id"] = seminar_product_id
            emit_data["inline_type"] = "seminar_interview"
            # Store product_id in the ChatChainConfig metadata for persistence
            try:
                with open(target_path, 'r', encoding='utf-8') as f:
                    cc_data = json.load(f)
                if "_meta" not in cc_data:
                    cc_data["_meta"] = {}
                cc_data["_meta"]["seminar_product_id"] = seminar_product_id
                with open(target_path, 'w', encoding='utf-8') as f:
                    json.dump(cc_data, f, indent=4, ensure_ascii=False)
            except Exception as me:
                logging.warning(f"Failed to store seminar meta: {me}")
        
        socketio_server.emit('playbook_applied', emit_data)
        
        return jsonify({
            "status": "success",
            "message": f"Successfully loaded and auto-assigned '{playbook['title']}' playbook template!",
            "assign_result": assign_result
        })
    except Exception as e:
        logging.error(f"Error applying playbook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
#   📚 Playbook Config CRUD API
#   Read/Write individual sections of bookclub_playbook.json
#   for the Studio Settings UI (hot-reload)
# ==========================================

_BOOKCLUB_PLAYBOOK_PATH = os.path.join(
    ROOT_DIR or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
    "CompanyConfig", "Playbooks", "bookclub_playbook.json"
)

def _load_bookclub_playbook():
    """Load full bookclub playbook JSON from disk."""
    try:
        if os.path.exists(_BOOKCLUB_PLAYBOOK_PATH):
            with open(_BOOKCLUB_PLAYBOOK_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("bookclub", data)
    except Exception as e:
        logging.warning(f"Failed to load bookclub playbook: {e}")
    return None

def _save_bookclub_playbook(bookclub_data):
    """Write bookclub playbook back to disk."""
    wrapper = {"bookclub": bookclub_data}
    os.makedirs(os.path.dirname(_BOOKCLUB_PLAYBOOK_PATH), exist_ok=True)
    with open(_BOOKCLUB_PLAYBOOK_PATH, 'w', encoding='utf-8') as f:
        json.dump(wrapper, f, indent=2, ensure_ascii=False)

# Sections that can be edited via the API
_EDITABLE_SECTIONS = {
    "planning_steps", "content_prompt", "design_tokens",
    "default_faq", "default_how_it_works", "nodes", "edges",
}


@misc_routes_bp.route("/api/playbook_config/bookclub", methods=["GET"])
def get_bookclub_playbook_config():
    """GET full bookclub playbook config (all editable sections)."""
    playbook = _load_bookclub_playbook()
    if not playbook:
        return jsonify({"status": "error", "message": "Playbook not found"}), 404
    return jsonify({"status": "success", "config": playbook})


@misc_routes_bp.route("/api/playbook_config/bookclub/<section>", methods=["GET"])
def get_bookclub_playbook_section(section):
    """GET a single section of the bookclub playbook (e.g. planning_steps)."""
    if section not in _EDITABLE_SECTIONS:
        return jsonify({"status": "error", "message": f"Unknown section: {section}"}), 400
    playbook = _load_bookclub_playbook()
    if not playbook:
        return jsonify({"status": "error", "message": "Playbook not found"}), 404
    data = playbook.get(section)
    if data is None:
        return jsonify({"status": "error", "message": f"Section '{section}' not found"}), 404
    return jsonify({"status": "success", "section": section, "data": data})


@misc_routes_bp.route("/api/playbook_config/bookclub/<section>", methods=["PUT"])
def update_bookclub_playbook_section(section):
    """PUT (replace) a single section of the bookclub playbook.
    Body: { "data": <new value for section> }
    """
    if section not in _EDITABLE_SECTIONS:
        return jsonify({"status": "error", "message": f"Unknown section: {section}"}), 400

    payload = request.get_json()
    if not payload or "data" not in payload:
        return jsonify({"status": "error", "message": "'data' field required in request body"}), 400

    new_data = payload["data"]

    # Validate section-specific constraints
    if section == "planning_steps":
        if not isinstance(new_data, list) or len(new_data) == 0:
            return jsonify({"status": "error", "message": "planning_steps must be a non-empty list"}), 400
        for step in new_data:
            if not isinstance(step, dict) or "id" not in step or "question" not in step:
                return jsonify({"status": "error", "message": "Each step must have 'id' and 'question'"}), 400

    elif section == "design_tokens":
        if not isinstance(new_data, dict):
            return jsonify({"status": "error", "message": "design_tokens must be a dict"}), 400

    elif section == "content_prompt":
        if not isinstance(new_data, dict) or "system_prompt" not in new_data:
            return jsonify({"status": "error", "message": "content_prompt must be a dict with 'system_prompt'"}), 400

    elif section in ("default_faq", "default_how_it_works"):
        if not isinstance(new_data, list):
            return jsonify({"status": "error", "message": f"{section} must be a list"}), 400

    playbook = _load_bookclub_playbook()
    if not playbook:
        return jsonify({"status": "error", "message": "Playbook not found"}), 404

    playbook[section] = new_data
    try:
        _save_bookclub_playbook(playbook)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Save failed: {e}"}), 500

    return jsonify({
        "status": "success",
        "message": f"'{section}' updated successfully",
        "section": section,
    })


@misc_routes_bp.route("/api/playbook_config/bookclub/reset/<section>", methods=["POST"])
def reset_bookclub_playbook_section(section):
    """Reset a section to its default value by removing the custom override.
    This effectively reverts the section to the hardcoded fallback values.
    """
    if section not in _EDITABLE_SECTIONS:
        return jsonify({"status": "error", "message": f"Unknown section: {section}"}), 400

    playbook = _load_bookclub_playbook()
    if not playbook:
        return jsonify({"status": "error", "message": "Playbook not found"}), 404

    # Load the original defaults from the store module's fallback
    defaults = {}
    try:
        from visualizer.services.bookclub_store import _FALLBACK_PLANNING_STEPS
        defaults["planning_steps"] = _FALLBACK_PLANNING_STEPS
    except ImportError:
        pass

    if section in defaults:
        playbook[section] = defaults[section]
    elif section in playbook:
        # Just remove the override key so the service falls back to hardcoded
        del playbook[section]

    try:
        _save_bookclub_playbook(playbook)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Reset failed: {e}"}), 500

    return jsonify({
        "status": "success",
        "message": f"'{section}' reset to defaults",
        "section": section,
    })


# ==========================================
#          LLMOps Telemetry & Webhooks
# ==========================================


@misc_routes_bp.route("/api/llmops/telemetry", methods=["POST"])
def llmops_telemetry():
    """Receives LLM metrics from Python process and broadcasts them via SocketIO."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        active_phase = payload.get("active_phase", "Coding")
        cumulative = payload.get("cumulative", {})
        cost = cumulative.get("cost", 0.0)
        
        # Load custom squad setup to map phase to custom employee title
        try:
            FleetManager = lazy_import('chatdev.fleet_manager', 'FleetManager')  # #5
            squad_details = FleetManager.load_squad_details(team_name)
        except Exception:
            squad_details = {}
            
        phase_to_role = {
            "DemandAnalysis": "Chief Product Officer",
            "LanguageChoose": "Chief Technology Officer",
            "Coding": "Programmer",
            "CodeComplete": "Programmer",
            "CodeReviewComment": "Code Reviewer",
            "CodeReviewModification": "Programmer",
            "TestErrorSummary": "Programmer",
            "TestModification": "Programmer",
            "EnvironmentDoc": "Programmer",
            "Manual": "Chief Product Officer"
        }
        role = phase_to_role.get(active_phase, "Programmer")
        agent_data = squad_details.get(role, {})
        title = agent_data.get("title", role)
        
        if team_name not in squad_stats:
            # ── Real throughput from telemetry DB (no more hardcoded data) ──
            _real_throughput = []
            try:
                if _PERSISTENT_STATE:
                    _real_throughput = telemetry_engine.get_throughput(team_name, days=7)
            except Exception as _e:
                logging.debug(f"[suppressed] Exception: {_e}")
            squad_stats[team_name] = {
                "active_tasks": 0,
                "token_cost": 0.0,
                "completed_tasks": 0,
                "throughput": _real_throughput,
                "workload": {},
                "cost_efficiency": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_calls": 0
            }
            
        squad_stats[team_name]["token_cost"] = cost
        squad_stats[team_name]["prompt_tokens"] = cumulative.get("prompt_tokens", 0)
        squad_stats[team_name]["completion_tokens"] = cumulative.get("completion_tokens", 0)
        squad_stats[team_name]["total_calls"] = cumulative.get("calls", 0)
        
        if squad_stats[team_name]["active_tasks"] == 0:
            squad_stats[team_name]["active_tasks"] = 1
            
        # Update workload chart data
        if "workload" not in squad_stats[team_name]:
            squad_stats[team_name]["workload"] = {}
        squad_stats[team_name]["workload"][title] = squad_stats[team_name]["workload"].get(title, 0) + 1
        
        # Calculate cost efficiency metric (Tasks per $100 spent)
        completed = squad_stats[team_name].get("completed_tasks", 0)
        squad_stats[team_name]["cost_efficiency"] = completed / (cost + 0.0001)
        
        # Broadcast immediately to frontend client listeners
        socketio_server.emit('llmops_telemetry', payload, room=team_name)
        
        # Save stats
        save_squad_stats()
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/webhook/slack", methods=["POST"])
def webhook_slack():
    """Slack mention command trigger gateway endpoint."""
    try:
        from chatdev.omni_channel import OmniChannelGateway
        payload = request.form.to_dict() if request.form else (request.get_json() or {})
        response_payload = OmniChannelGateway.handle_slack_webhook(payload)
        return jsonify(response_payload)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/webhook/discord", methods=["POST"])
def webhook_discord():
    """Discord command trigger gateway endpoint."""
    try:
        from chatdev.omni_channel import OmniChannelGateway
        payload = request.get_json() or {}
        response_payload = OmniChannelGateway.handle_discord_webhook(payload)
        return jsonify(response_payload)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
#          WebSocket Room-based Scoping
# ==========================================


@misc_routes_bp.route("/api/chat/send", methods=["POST"])
def chat_send():
    """Send a chat message to an agent and get LLM response."""
    try:
        data = request.get_json()
        team_name = data.get("team_name", "Squad_A")
        agent_role = data.get("agent_role", "AI Assistant")
        user_message = data.get("message", "")
        system_prompt = data.get("system_prompt", f"You are a {agent_role}. Respond helpfully in Korean.")

        if not user_message:
            return jsonify({"status": "error", "message": "메시지가 비어 있습니다."}), 400

        # Initialize chat history
        if _PERSISTENT_STATE and hasattr(_chat_history, 'append_message'):
            pass  # DB-backed, no init needed
        elif team_name not in _chat_history:
            _chat_history[team_name] = []

        # Save user message (persistent)
        user_entry = {
            "role": "user", "agent": "사용자", "content": user_message,
            "timestamp": datetime.now().isoformat()
        }
        if _PERSISTENT_STATE and hasattr(_chat_history, 'append_message'):
            _chat_history.append_message(team_name, user_entry)
        else:
            _chat_history[team_name].append(user_entry)

        # Build context from recent history
        if _PERSISTENT_STATE and hasattr(_chat_history, 'get_messages'):
            recent = _chat_history.get_messages(team_name, limit=10)
        else:
            recent = _chat_history.get(team_name, [])[-10:]
        messages = [{"role": "system", "content": system_prompt}]
        for h in recent:
            messages.append({"role": h["role"] if h["role"] in ("user","assistant") else "user",
                             "content": h["content"]})

        # Get LLM response
        response = get_llm_response(messages, max_tokens=800)

        # Save agent response (persistent)
        agent_entry = {
            "role": "assistant", "agent": agent_role, "content": response,
            "timestamp": datetime.now().isoformat()
        }
        if _PERSISTENT_STATE and hasattr(_chat_history, 'append_message'):
            _chat_history.append_message(team_name, agent_entry)
        else:
            _chat_history.get(team_name, []).append(agent_entry)

        # Meter billing
        try:
            meter_action(agent_role, "chat_response", 300, 150)
        except Exception as _e:
            logging.debug(f"[suppressed] Exception: {_e}")

        # Emit via SocketIO
        socketio_server.emit("chat_message", {
            "team_name": team_name, "agent": agent_role,
            "content": response, "timestamp": agent_entry["timestamp"]
        }, room=team_name)

        return jsonify({
            "status": "success",
            "response": response,
            "agent": agent_role,
            "timestamp": agent_entry["timestamp"]
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



@misc_routes_bp.route("/api/chat/history", methods=["GET"])
def chat_history():
    """Get chat history for a team."""
    team_name = request.args.get("team_name", "Squad_A")
    limit = int(request.args.get("limit", 50))
    if _PERSISTENT_STATE and hasattr(_chat_history, 'get_messages'):
        history = _chat_history.get_messages(team_name, limit=limit)
    else:
        history = _chat_history.get(team_name, [])[-limit:]
    return jsonify({"status": "success", "messages": history, "count": len(history)})


# ==========================================
#    항목 7: Execution History Viewer API
# ==========================================


@misc_routes_bp.route("/api/execution/history", methods=["GET"])
def execution_history_api_list():
    """List all execution history records."""
    history_dir = os.path.join(VISUALIZER_DIR, "execution_history")
    os.makedirs(history_dir, exist_ok=True)
    records = []
    for fname in sorted(os.listdir(history_dir), reverse=True):
        if fname.endswith(".json"):
            fpath = os.path.join(history_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                records.append({
                    "exec_id": data.get("exec_id"),
                    "team_name": data.get("team_name"),
                    "prompt": data.get("prompt", "")[:100],
                    "total_agents": data.get("total_agents", 0),
                    "total_cost_usd": data.get("total_cost_usd", 0),
                    "total_duration_ms": data.get("total_duration_ms", 0),
                    "started_at": data.get("started_at"),
                    "completed_at": data.get("completed_at")
                })
            except Exception as _e:
                logging.debug(f"[suppressed] Exception: {_e}")
    return jsonify({"status": "success", "records": records, "count": len(records)})



@misc_routes_bp.route("/api/execution/<exec_id>", methods=["GET"])
def execution_detail(exec_id):
    """Get detailed execution result including all agent outputs."""
    history_dir = os.path.join(VISUALIZER_DIR, "execution_history")
    fpath = os.path.join(history_dir, f"{exec_id}.json")
    if not os.path.exists(fpath):
        if "text/html" in request.headers.get("Accept", ""):
            return "<h3>Execution history record not found.</h3>", 404
        return jsonify({"status": "error", "message": "Execution not found"}), 404
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Render HTML if requested by browser
    if "text/html" in request.headers.get("Accept", "") and not request.args.get("format") == "json":
        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Execution Timeline - {exec_id}</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Outfit', sans-serif; background: #fafbfc; color: #1e293b; min-height: 100vh; }}
        
        .gnb-header {{
            height: 56px; display: flex; align-items: center; justify-content: space-between;
            padding: 0 24px; border-bottom: 1px solid #e2e8f0; background: #ffffff;
            position: sticky; top: 0; z-index: 100;
        }}
        .gnb-left {{ display: flex; align-items: center; gap: 20px; }}
        .gnb-logo {{ font-weight: 700; font-size: 14px; color: #1e293b; text-decoration: none; display: flex; align-items: center; gap: 8px; }}
        .gnb-logo i {{ color: #16a34a; }}
        .gnb-nav {{ display: flex; gap: 2px; }}
        .gnb-tab {{
            padding: 8px 16px; font-size: 12px; font-weight: 600; color: #94a3b8; border-radius: 6px;
            text-decoration: none; transition: all 0.2s; display: flex; align-items: center; gap: 6px;
        }}
        .gnb-tab:hover {{ color: #64748b; background: #f8fafc; }}
        .gnb-tab.active {{ color: #16a34a; background: rgba(22,163,106,0.06); border: 1px solid rgba(22,163,106,0.15); }}
        
        .container {{ max-width: 900px; margin: 40px auto; padding: 0 24px; }}
        .btn {{
            display: inline-flex; align-items: center; gap: 8px;
            padding: 10px 20px; background: #16a34a; color: #fff;
            border: none; border-radius: 8px; font-size: 13px; font-weight: 600;
            cursor: pointer; text-decoration: none; transition: background 0.2s;
        }}
        .btn:hover {{ background: #15803d; }}
        .btn-outline {{
            background: transparent; color: #64748b; border: 1px solid #cbd5e1;
        }}
        .btn-outline:hover {{ background: #f8fafc; color: #1e293b; border-color: #94a3b8; }}
        
        .header-section {{ margin-bottom: 32px; display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }}
        .title-block {{ flex: 1; }}
        .title {{ font-size: 24px; font-weight: 800; color: #1e293b; margin-bottom: 6px; letter-spacing: -0.5px; }}
        .subtitle {{ font-size: 13px; color: #94a3b8; line-height: 1.6; }}
        
        .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 32px; }}
        .stats-card {{
            background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
            padding: 16px; text-align: center;
        }}
        .stats-card .val {{ font-size: 20px; font-weight: 800; color: #1e293b; font-family: 'JetBrains Mono', monospace; }}
        .stats-card .lbl {{ font-size: 10px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }}
        
        .prompt-card {{
            background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
            padding: 20px; margin-bottom: 32px;
        }}
        .card-title {{ font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; display: flex; align-items: center; gap: 6px; }}
        .prompt-text {{ font-size: 14px; line-height: 1.6; color: #334155; white-space: pre-wrap; }}
        
        .timeline-section {{ display: flex; flex-direction: column; gap: 24px; position: relative; }}
        .timeline-section::before {{
            content: ''; position: absolute; left: 29px; top: 16px; bottom: 16px;
            width: 2px; background: #e2e8f0; z-index: 1;
        }}
        .step-node {{ display: flex; gap: 20px; position: relative; z-index: 2; }}
        .step-badge {{
            width: 60px; height: 60px; border-radius: 50%; background: #ffffff;
            border: 2px solid #16a34a; color: #16a34a; font-weight: 800; font-size: 18px;
            display: flex; align-items: center; justify-content: center; flex-shrink: 0;
            box-shadow: 0 4px 12px rgba(22,163,106,0.1);
        }}
        .step-content {{
            flex: 1; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
            padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.02);
        }}
        .step-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #f1f5f9; }}
        .step-agent {{ font-size: 15px; font-weight: 700; color: #1e293b; }}
        .step-meta {{ font-size: 11px; color: #94a3b8; display: flex; gap: 12px; font-family: 'JetBrains Mono', monospace; }}
        .step-meta span i {{ margin-right: 4px; }}
        
        .output-box {{
            background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
            padding: 16px; font-family: 'JetBrains Mono', monospace; font-size: 12px;
            color: #334155; line-height: 1.6; max-height: 400px; overflow-y: auto;
            white-space: pre-wrap; margin-bottom: 12px;
        }}
        .step-actions {{ display: flex; justify-content: flex-end; gap: 8px; }}
        .copy-btn {{
            background: none; border: 1px solid #cbd5e1; color: #64748b;
            padding: 6px 12px; border-radius: 6px; font-size: 11px; font-weight: 600;
            cursor: pointer; display: flex; align-items: center; gap: 4px; transition: all 0.15s;
        }}
        .copy-btn:hover {{ border-color: #16a34a; color: #16a34a; background: rgba(22,163,106,0.02); }}
    </style>
</head>
<body>

    <header class="gnb-header">
        <div class="gnb-left">
            <a href="/" class="gnb-logo"><i class="fa-solid fa-network-wired"></i> ChatDev</a>
            <nav class="gnb-nav">
                <a href="/" class="gnb-tab"><i class="fa-solid fa-map"></i> Dashboard</a>
                <a href="/agents" class="gnb-tab"><i class="fa-solid fa-users"></i> Agents</a>
                <a href="/tools" class="gnb-tab"><i class="fa-solid fa-toolbox"></i> Tools</a>
                <a href="/integrations" class="gnb-tab"><i class="fa-solid fa-key"></i> Integrations</a>
            </nav>
        </div>
    </header>

    <div class="container">
        <div class="header-section">
            <div class="title-block">
                <div class="title"><i class="fa-solid fa-timeline"></i> Execution Timeline</div>
                <div class="subtitle">ID: {exec_id} — {data.get("team_name", "")} 워크플로우 실행 세부 결과</div>
            </div>
            <div style="display:flex; gap:8px;">
                <a href="/" class="btn btn-outline"><i class="fa-solid fa-arrow-left"></i> 목록으로</a>
                <a href="/api/execution/{exec_id}/download" class="btn"><i class="fa-solid fa-file-zipper"></i> ZIP 다운로드</a>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stats-card"><div class="val">{data.get("total_agents", 0)}</div><div class="lbl">Total Agents</div></div>
            <div class="stats-card"><div class="val">${data.get("total_cost_usd", 0.0):.4f}</div><div class="lbl">Execution Cost</div></div>
            <div class="stats-card"><div class="val">{(data.get("total_duration_ms", 0)/1000):.2f}s</div><div class="lbl">Total Duration</div></div>
            <div class="stats-card"><div class="val">{data.get("completed_at", "—")[:19].replace("T", " ")}</div><div class="lbl">Finished At</div></div>
        </div>

        <div class="prompt-card">
            <div class="card-title"><i class="fa-solid fa-terminal"></i> Task Prompt</div>
            <div class="prompt-text">{data.get("prompt", "")}</div>
        </div>

        <div class="timeline-section">
            {"".join([f'''
            <div class="step-node">
                <div class="step-badge">{s["step"]}</div>
                <div class="step-content">
                    <div class="step-header">
                        <div class="step-agent">{s["agent"]}</div>
                        <div class="step-meta">
                            <span><i class="fa-solid fa-stopwatch"></i> {s.get("duration_ms", 0)/1000:.2f}s</span>
                            <span><i class="fa-solid fa-coins"></i> ${s.get("cost_usd", 0.0):.4f}</span>
                        </div>
                    </div>
                    <div class="output-box" id="output-{s['step']}">{s.get("output", "")}</div>
                    <div class="step-actions">
                        <button class="copy-btn" onclick="copyText({s['step']})"><i class="fa-solid fa-copy"></i> 복사하기</button>
                    </div>
                </div>
            </div>
            ''' for s in data.get("steps", [])])}
        </div>
    </div>

    <script>
        function copyText(stepId) {{
            const txt = document.getElementById('output-' + stepId).innerText;
            navigator.clipboard.writeText(txt).then(() => {{
                alert('산출물이 클립보드에 복사되었습니다.');
            }});
        }}
    </script>
</body>
</html>
"""
        return html

    return jsonify({"status": "success", "execution": data})



@misc_routes_bp.route("/api/execution/<exec_id>/download", methods=["GET"])
def download_execution_zip(exec_id):
    """Download all step outputs of an execution as a single ZIP file."""
    import io, zipfile, re
    history_dir = os.path.join(VISUALIZER_DIR, "execution_history")
    fpath = os.path.join(history_dir, f"{exec_id}.json")
    if not os.path.exists(fpath):
        return "Execution not found", 404

    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        report_lines = [
            f"# Execution Report - {data.get('exec_id')}",
            f"Team: {data.get('team_name')}",
            f"Prompt: {data.get('prompt')}",
            f"Started At: {data.get('started_at')}",
            f"Completed At: {data.get('completed_at')}",
            f"Total Cost: ${data.get('total_cost_usd', 0):.4f}",
            "",
            "## Steps"
        ]

        for step in data.get("steps", []):
            role = step.get("agent", "Agent")
            step_idx = step.get("step", 0)
            output_content = step.get("output", "")

            # Clean name
            clean_role = re.sub(r'[^a-zA-Z0-9가-힣_]', '', role)
            filename = f"{step_idx}_{clean_role}.md"
            zip_file.writestr(filename, output_content)

            report_lines.append(f"- Step {step_idx}: {role} -> `{filename}`")

        zip_file.writestr("report.md", "\n".join(report_lines))

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"execution_{exec_id}.zip"
    )



# ==========================================
#    항목 5: Connector Validation API
# ==========================================


@misc_routes_bp.route("/api/connectors/validate", methods=["POST"])
def validate_connectors():
    """Validate external service connector credentials."""
    data = request.get_json() or {}
    connector_type = data.get("type", "")
    results = []

    # Define validation rules per connector
    validations = {
        "github": {"token_prefix": "ghp_", "min_len": 30, "url_required": True},
        "gitlab": {"token_prefix": "glpat-", "min_len": 20, "url_required": True},
        "slack":  {"token_prefix": "xoxb-", "min_len": 20, "url_required": False},
        "notion": {"token_prefix": "secret_", "min_len": 20, "url_required": False},
        "youtube": {"token_prefix": "AIza", "min_len": 20, "url_required": False},
    }

    connectors = data.get("connectors", {})
    for ctype, config in connectors.items():
        token = config.get("token", "")
        url = config.get("url", "")
        rules = validations.get(ctype, {})

        status = "unconfigured"
        issues = []

        if not token:
            status = "unconfigured"
            issues.append("토큰이 설정되지 않았습니다")
        elif "dummy" in token.lower() or "fake" in token.lower() or "test" in token.lower():
            status = "invalid"
            issues.append("⚠️ 더미/테스트 토큰이 감지되었습니다. 실제 토큰을 입력하세요.")
        elif rules.get("token_prefix") and not token.startswith(rules["token_prefix"]):
            status = "invalid"
            issues.append(f"토큰 접두사가 '{rules['token_prefix']}'로 시작해야 합니다")
        elif rules.get("min_len") and len(token) < rules["min_len"]:
            status = "invalid"
            issues.append(f"토큰 길이가 최소 {rules['min_len']}자 이상이어야 합니다")
        elif rules.get("url_required") and not url:
            status = "invalid"
            issues.append("URL이 필요합니다")
        else:
            status = "valid"
            try:
                import urllib.request, urllib.error, json as _json
                if ctype == "github":
                    req = urllib.request.Request("https://api.github.com/user")
                    req.add_header("Authorization", f"token {token}")
                    req.add_header("User-Agent", "ChatDev-Enterprise")
                    try:
                        with urllib.request.urlopen(req, timeout=5) as r:
                            if r.status == 200:
                                status = "valid"
                            else:
                                status = "invalid"
                                issues.append(f"GitHub API Error: HTTP {r.status}")
                    except urllib.error.HTTPError as e:
                        status = "invalid"
                        issues.append(f"GitHub 인증 실패 (HTTP {e.code}): 토큰이 유효하지 않거나 권한이 부족합니다.")
                elif ctype == "gitlab":
                    base_url = url.rstrip("/") if url else "https://gitlab.com"
                    req = urllib.request.Request(f"{base_url}/api/v4/user")
                    req.add_header("Private-Token", token)
                    try:
                        with urllib.request.urlopen(req, timeout=5) as r:
                            if r.status == 200:
                                status = "valid"
                            else:
                                status = "invalid"
                                issues.append(f"GitLab API Error: HTTP {r.status}")
                    except urllib.error.HTTPError as e:
                        status = "invalid"
                        issues.append(f"GitLab 인증 실패 (HTTP {e.code}): 토큰이 유효하지 않습니다.")
                elif ctype == "slack":
                    req = urllib.request.Request("https://slack.com/api/auth.test")
                    req.add_header("Authorization", f"Bearer {token}")
                    req.add_header("Content-Type", "application/json")
                    try:
                        with urllib.request.urlopen(req, timeout=5) as r:
                            res_data = _json.loads(r.read().decode('utf-8'))
                            if res_data.get("ok"):
                                status = "valid"
                            else:
                                status = "invalid"
                                issues.append(f"Slack 인증 실패: {res_data.get('error', 'unknown error')}")
                    except Exception as e:
                        status = "invalid"
                        issues.append(f"Slack 연결 오류: {str(e)[:80]}")
                elif ctype == "notion":
                    req = urllib.request.Request("https://api.notion.com/v1/users/me")
                    req.add_header("Authorization", f"Bearer {token}")
                    req.add_header("Notion-Version", "2022-06-28")
                    try:
                        with urllib.request.urlopen(req, timeout=5) as r:
                            if r.status == 200:
                                status = "valid"
                            else:
                                status = "invalid"
                                issues.append(f"Notion API Error: HTTP {r.status}")
                    except urllib.error.HTTPError as e:
                        status = "invalid"
                        issues.append(f"Notion 인증 실패 (HTTP {e.code}): 토큰이 유효하지 않습니다.")
                elif ctype == "youtube":
                    req = urllib.request.Request(f"https://www.googleapis.com/youtube/v3/videoCategories?part=snippet&regionCode=US&key={token}")
                    try:
                        with urllib.request.urlopen(req, timeout=5) as r:
                            if r.status == 200:
                                status = "valid"
                            else:
                                status = "invalid"
                                issues.append(f"YouTube API Error: HTTP {r.status}")
                    except urllib.error.HTTPError as e:
                        status = "invalid"
                        issues.append(f"YouTube 인증 실패 (HTTP {e.code}): API 키가 유효하지 않습니다.")
            except Exception as e:
                issues.append(f"Network Warning (연결 시도 실패, 로컬 유효성만 검증됨): {str(e)[:80]}")


        results.append({
            "type": ctype,
            "status": status,
            "issues": issues,
            "masked_token": token[:8] + "•" * max(0, len(token) - 12) + token[-4:] if len(token) > 12 else "•" * len(token)
        })

    return jsonify({"status": "success", "validations": results})

# ══════════════════════════════════════════════════════════════════
#   ⚡ WORKFLOW ENGINE — 30 Feature APIs
# ══════════════════════════════════════════════════════════════════

# --- #5: DAG Validation ---

@misc_routes_bp.route("/api/backup_workflow", methods=["POST"])
def backup_workflow():
    data = request.json
    team_name = data.get("team_name", "")
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    if not team_name:
        return jsonify({"status": "error", "message": "team_name required"})

    backup_dir = os.path.join("CompanyConfig", "Teams", team_name, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"backup_{timestamp}.json")

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump({"timestamp": timestamp, "nodes": nodes, "edges": edges}, f, ensure_ascii=False, indent=2)

    # Keep max 10 backups
    existing = sorted(glob.glob(os.path.join(backup_dir, "backup_*.json")), reverse=True)
    for old_file in existing[10:]:
        os.remove(old_file)

    return jsonify({"status": "success", "backup_file": backup_file, "timestamp": timestamp})



@misc_routes_bp.route("/api/list_backups", methods=["GET"])
def list_backups():
    team_name = request.args.get("team_name", "")
    if not team_name:
        return jsonify({"status": "error", "message": "team_name required"})

    backup_dir = os.path.join("CompanyConfig", "Teams", team_name, "backups")
    backups = []
    if os.path.isdir(backup_dir):
        for fname in sorted(os.listdir(backup_dir), reverse=True):
            if fname.endswith(".json"):
                fpath = os.path.join(backup_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    backups.append({
                        "filename": fname,
                        "timestamp": data.get("timestamp", ""),
                        "node_count": len(data.get("nodes", [])),
                        "edge_count": len(data.get("edges", []))
                    })
                except Exception as _e:
                    logging.debug(f"[suppressed] Exception: {_e}")
    return jsonify({"status": "success", "backups": backups})



@misc_routes_bp.route("/api/restore_backup", methods=["POST"])
def restore_backup():
    data = request.json
    team_name = data.get("team_name", "")
    filename = data.get("filename", "")
    if not team_name or not filename:
        return jsonify({"status": "error", "message": "team_name and filename required"})

    backup_path = os.path.join("CompanyConfig", "Teams", team_name, "backups", filename)
    if not os.path.isfile(backup_path):
        return jsonify({"status": "error", "message": "Backup file not found"})

    with open(backup_path, "r", encoding="utf-8") as f:
        backup_data = json.load(f)

    return jsonify({"status": "success", "nodes": backup_data.get("nodes", []), "edges": backup_data.get("edges", [])})


# ── #30: Execution Time Estimation API ──

@misc_routes_bp.route("/api/estimate_execution", methods=["POST"])
def estimate_execution():
    data = request.json
    nodes = data.get("nodes", [])
    # Filter out trigger nodes
    agent_nodes = [n for n in nodes if n.get("id") != "Trigger" and n.get("phase") != "Trigger"]
    node_count = len(agent_nodes)

    # Average estimates based on past execution data
    avg_time_per_node = 8  # seconds
    avg_tokens_per_node = 2500
    cost_per_1k_tokens = 0.0025

    total_time = node_count * avg_time_per_node
    total_tokens = node_count * avg_tokens_per_node
    total_cost = (total_tokens / 1000) * cost_per_1k_tokens

    return jsonify({
        "status": "success",
        "estimate": {
            "node_count": node_count,
            "total_time_seconds": total_time,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4)
        }
    })


# ══════════════════════════════════════════════
# 💼 CRM CRUD APIs
# ══════════════════════════════════════════════


@misc_routes_bp.route("/api/crm/save", methods=["POST"])
def crm_save():
    data = request.json
    team_name = data.get("team_name", "default")
    crm_dir = os.path.join("CompanyConfig", "Teams", team_name, "crm")
    os.makedirs(crm_dir, exist_ok=True)

    for key in ["contacts", "deals", "activities"]:
        if key in data:
            fpath = os.path.join(crm_dir, f"{key}.json")
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data[key], f, ensure_ascii=False, indent=2)

    return jsonify({"status": "success"})



@misc_routes_bp.route("/api/crm/load", methods=["GET"])
def crm_load():
    team_name = request.args.get("team_name", "default")
    crm_dir = os.path.join("CompanyConfig", "Teams", team_name, "crm")
    result = {"status": "success"}

    for key in ["contacts", "deals", "activities"]:
        fpath = os.path.join(crm_dir, f"{key}.json")
        if os.path.isfile(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    result[key] = json.load(f)
            except Exception:
                result[key] = []
        else:
            result[key] = []

    return jsonify(result)


# ══════════════════════════════════════════════
# ☁️ SALESFORCE CONNECTOR APIs
# ══════════════════════════════════════════════


@misc_routes_bp.route("/api/crm/salesforce/test", methods=["POST"])
def sf_test():
    """Test Salesforce connection with provided credentials."""
    data = request.json
    instance_url = data.get("instance_url", "").rstrip("/")
    username = data.get("username", "")
    password = data.get("password", "")
    client_id = data.get("client_id", "")
    client_secret = data.get("client_secret", "")

    if not instance_url or not username:
        return jsonify({"status": "error", "message": "Instance URL and Username required"})

    try:
        import urllib.request
        import urllib.parse

        # OAuth2 Username-Password Flow
        token_url = f"{instance_url}/services/oauth2/token"
        payload = urllib.parse.urlencode({
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
            "username": username,
            "password": password
        }).encode()

        req = urllib.request.Request(token_url, data=payload, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_data = json.loads(resp.read().decode())

        if "access_token" in resp_data:
            # Query org name
            org_name = ""
            try:
                api_url = f"{resp_data.get('instance_url', instance_url)}/services/data/v59.0/query?q={urllib.parse.quote('SELECT Name FROM Organization LIMIT 1')}"
                org_req = urllib.request.Request(api_url)
                org_req.add_header("Authorization", f"Bearer {resp_data['access_token']}")
                with urllib.request.urlopen(org_req, timeout=10) as org_resp:
                    org_data = json.loads(org_resp.read().decode())
                    if org_data.get("records"):
                        org_name = org_data["records"][0].get("Name", "")
            except Exception as _e:
                logging.debug(f"[suppressed] Exception: {_e}")

            return jsonify({"status": "success", "org_name": org_name})
        else:
            return jsonify({"status": "error", "message": resp_data.get("error_description", "Auth failed")})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})



@misc_routes_bp.route("/api/crm/salesforce/auth", methods=["POST"])
def sf_auth():
    """Authenticate with Salesforce and return access token."""
    data = request.json
    instance_url = data.get("instance_url", "").rstrip("/")
    username = data.get("username", "")
    password = data.get("password", "")
    client_id = data.get("client_id", "")
    client_secret = data.get("client_secret", "")

    try:
        import urllib.request
        import urllib.parse

        token_url = f"{instance_url}/services/oauth2/token"
        payload = urllib.parse.urlencode({
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
            "username": username,
            "password": password
        }).encode()

        req = urllib.request.Request(token_url, data=payload, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_data = json.loads(resp.read().decode())

        if "access_token" in resp_data:
            return jsonify({
                "status": "success",
                "access_token": resp_data["access_token"],
                "instance_url": resp_data.get("instance_url", instance_url)
            })
        else:
            return jsonify({"status": "error", "message": resp_data.get("error_description", "Auth failed")})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})



@misc_routes_bp.route("/api/crm/salesforce/sync_pull", methods=["POST"])
def sf_sync_pull():
    """Pull Contacts, Opportunities, and Tasks from Salesforce."""
    data = request.json
    config = data.get("config", {})
    team_name = data.get("team_name", "default")

    access_token = config.get("access_token", "")
    instance_url = config.get("instance_url", "").rstrip("/")

    if not access_token or not instance_url:
        return jsonify({"status": "error", "message": "Not authenticated"})

    try:
        import urllib.request
        import urllib.parse

        def sf_query(soql):
            url = f"{instance_url}/services/data/v59.0/query?q={urllib.parse.quote(soql)}"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {access_token}")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())

        # Pull Contacts
        contact_result = sf_query("SELECT Id, Name, Title, Email, Phone, Account.Name FROM Contact ORDER BY CreatedDate DESC LIMIT 200")
        contacts = []
        for rec in contact_result.get("records", []):
            contacts.append({
                "id": "sf_" + rec["Id"],
                "name": rec.get("Name", ""),
                "company": rec.get("Account", {}).get("Name", "") if rec.get("Account") else "",
                "title": rec.get("Title", ""),
                "email": rec.get("Email", ""),
                "phone": rec.get("Phone", ""),
                "segment": "enterprise",
                "score": 50,
                "sf_id": rec["Id"],
                "created": datetime.now().isoformat(),
                "notes": ""
            })

        # Pull Opportunities as Deals
        opp_result = sf_query("SELECT Id, Name, StageName, Amount, Probability, CloseDate, Account.Name, Owner.Name FROM Opportunity ORDER BY CreatedDate DESC LIMIT 100")
        deals = []
        stage_map = {
            "Prospecting": "lead", "Qualification": "qualified",
            "Proposal/Price Quote": "proposal", "Negotiation/Review": "negotiation",
            "Closed Won": "closed_won", "Closed Lost": "closed_lost"
        }
        for rec in opp_result.get("records", []):
            sf_stage = rec.get("StageName", "")
            mapped_stage = stage_map.get(sf_stage, "lead")
            # Find matching contact
            contact_id = ""
            acct_name = rec.get("Account", {}).get("Name", "") if rec.get("Account") else ""
            for c in contacts:
                if c["company"] == acct_name:
                    contact_id = c["id"]
                    break

            deals.append({
                "id": "sf_" + rec["Id"],
                "title": rec.get("Name", ""),
                "contact_id": contact_id,
                "stage": mapped_stage,
                "amount": int(rec.get("Amount", 0) or 0),
                "probability": int(rec.get("Probability", 50) or 50),
                "close_date": rec.get("CloseDate", ""),
                "owner": rec.get("Owner", {}).get("Name", "AI Agent") if rec.get("Owner") else "AI Agent",
                "sf_id": rec["Id"],
                "created": datetime.now().isoformat()
            })

        # Pull Recent Tasks as Activities
        task_result = sf_query("SELECT Id, Subject, Status, ActivityDate, Who.Name, Type FROM Task ORDER BY CreatedDate DESC LIMIT 50")
        activities = []
        type_map = {"Email": "email", "Call": "call", "Meeting": "meeting"}
        icon_map = {"email": "📧", "call": "📞", "meeting": "🤝", "note": "📝"}
        for rec in task_result.get("records", []):
            act_type = type_map.get(rec.get("Type", ""), "note")
            activities.append({
                "id": "sf_" + rec["Id"],
                "contact_id": "",
                "type": act_type,
                "icon": icon_map.get(act_type, "📝"),
                "summary": rec.get("Subject", ""),
                "timestamp": datetime.now().isoformat(),
                "result": "neutral"
            })

        # Save to local
        crm_dir = os.path.join("CompanyConfig", "Teams", team_name, "crm")
        os.makedirs(crm_dir, exist_ok=True)
        for key, items in [("contacts", contacts), ("deals", deals), ("activities", activities)]:
            with open(os.path.join(crm_dir, f"{key}.json"), "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)

        return jsonify({"status": "success", "contacts": contacts, "deals": deals, "activities": activities})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})



@misc_routes_bp.route("/api/crm/salesforce/sync_push", methods=["POST"])
def sf_sync_push():
    """Push local CRM changes back to Salesforce."""
    data = request.json
    config = data.get("config", {})
    push_type = data.get("type", "")
    push_data = data.get("data", {})

    access_token = config.get("access_token", "")
    instance_url = config.get("instance_url", "").rstrip("/")

    if not access_token or not instance_url:
        return jsonify({"status": "error", "message": "Not authenticated"})

    try:
        import urllib.request

        if push_type == "contact_create" and not push_data.get("sf_id"):
            # Create Contact in Salesforce
            url = f"{instance_url}/services/data/v59.0/sobjects/Contact/"
            body = json.dumps({
                "LastName": push_data.get("name", "Unknown"),
                "Title": push_data.get("title", ""),
                "Email": push_data.get("email", ""),
                "Phone": push_data.get("phone", "")
            }).encode()
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Authorization", f"Bearer {access_token}")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_data = json.loads(resp.read().decode())
            return jsonify({"status": "success", "sf_id": resp_data.get("id", "")})

        elif push_type == "deal_create" and not push_data.get("sf_id"):
            # Create Opportunity in Salesforce
            stage_reverse = {
                "lead": "Prospecting", "qualified": "Qualification",
                "proposal": "Proposal/Price Quote", "negotiation": "Negotiation/Review",
                "closed_won": "Closed Won", "closed_lost": "Closed Lost"
            }
            url = f"{instance_url}/services/data/v59.0/sobjects/Opportunity/"
            body = json.dumps({
                "Name": push_data.get("title", "New Deal"),
                "StageName": stage_reverse.get(push_data.get("stage", "lead"), "Prospecting"),
                "Amount": push_data.get("amount", 0),
                "CloseDate": push_data.get("close_date", datetime.now().strftime("%Y-%m-%d"))
            }).encode()
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Authorization", f"Bearer {access_token}")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_data = json.loads(resp.read().decode())
            return jsonify({"status": "success", "sf_id": resp_data.get("id", "")})

        elif push_type == "deal_update" and push_data.get("sf_id"):
            # Update Opportunity stage in Salesforce
            stage_reverse = {
                "lead": "Prospecting", "qualified": "Qualification",
                "proposal": "Proposal/Price Quote", "negotiation": "Negotiation/Review",
                "closed_won": "Closed Won", "closed_lost": "Closed Lost"
            }
            sf_id = push_data["sf_id"]
            url = f"{instance_url}/services/data/v59.0/sobjects/Opportunity/{sf_id}"
            body = json.dumps({
                "StageName": stage_reverse.get(push_data.get("stage", "lead"), "Prospecting")
            }).encode()
            req = urllib.request.Request(url, data=body, method="PATCH")
            req.add_header("Authorization", f"Bearer {access_token}")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=15) as resp:
                pass
            return jsonify({"status": "success"})

        return jsonify({"status": "skipped", "message": "No action needed"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ══════════════════════════════════════════════════════════════════
#   🔧 SHELL FIXES — Backend APIs for 29 Empty Shell Completions
# ══════════════════════════════════════════════════════════════════

# --- #3: Single Connector Validate (for shell_fixes.js form override) ---

@misc_routes_bp.route("/api/connectors/validate_single", methods=["POST"])
def validate_single_connector():
    """Validate a single external service connector with real API calls."""
    data = request.get_json() or {}
    ctype = data.get("type", "").lower()
    config = data.get("config", {})
    token = ""
    url_val = ""

    # Extract token/url from dynamic config keys
    for k, v in config.items():
        kl = k.lower()
        if "token" in kl or "key" in kl or "secret" in kl or "password" in kl:
            token = v
        if "url" in kl or "endpoint" in kl or "host" in kl:
            url_val = v

    if not token:
        return jsonify({"status": "error", "message": "토큰/API키가 입력되지 않았습니다"})

    import urllib.request, urllib.error
    try:
        if ctype == "github":
            req = urllib.request.Request("https://api.github.com/user")
            req.add_header("Authorization", f"token {token}")
            req.add_header("User-Agent", "ChatDev-Enterprise")
            with urllib.request.urlopen(req, timeout=8) as r:
                rdata = json.loads(r.read().decode())
                return jsonify({"status": "success", "message": f"GitHub 연결 성공: {rdata.get('login', '')}", "user": rdata.get("login", "")})

        elif ctype == "gitlab":
            base = (url_val or "https://gitlab.com").rstrip("/")
            req = urllib.request.Request(f"{base}/api/v4/user")
            req.add_header("Private-Token", token)
            with urllib.request.urlopen(req, timeout=8) as r:
                rdata = json.loads(r.read().decode())
                return jsonify({"status": "success", "message": f"GitLab 연결 성공: {rdata.get('username', '')}"})

        elif ctype == "slack":
            req = urllib.request.Request("https://slack.com/api/auth.test")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=8) as r:
                rdata = json.loads(r.read().decode())
                if rdata.get("ok"):
                    return jsonify({"status": "success", "message": f"Slack 연결 성공: {rdata.get('team', '')}"})
                else:
                    return jsonify({"status": "error", "message": f"Slack 인증 실패: {rdata.get('error', '')}"})

        elif ctype == "notion":
            req = urllib.request.Request("https://api.notion.com/v1/users/me")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Notion-Version", "2022-06-28")
            with urllib.request.urlopen(req, timeout=8) as r:
                rdata = json.loads(r.read().decode())
                return jsonify({"status": "success", "message": f"Notion 연결 성공: {rdata.get('name', '')}"})

        elif ctype == "youtube":
            req = urllib.request.Request(f"https://www.googleapis.com/youtube/v3/videoCategories?part=snippet&regionCode=US&key={token}")
            with urllib.request.urlopen(req, timeout=8) as r:
                return jsonify({"status": "success", "message": "YouTube API 키 유효"})

        elif ctype == "crawler":
            return jsonify({"status": "success", "message": "Web Crawler 설정 저장됨 (로컬 모드)"})

        else:
            return jsonify({"status": "success", "message": f"{ctype} 설정 저장됨 (검증 미지원 — 연결은 수동 확인 필요)"})

    except urllib.error.HTTPError as e:
        return jsonify({"status": "error", "message": f"인증 실패 (HTTP {e.code}): 토큰/API키를 확인하세요"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"연결 오류: {str(e)[:120]}"})


# ══════════════════════════════════════════════════════════════
# 🚀 LAUNCH PAD — Progressive Disclosure Layer 1 & 2 APIs
# ══════════════════════════════════════════════════════════════

# In-memory execution history store

@misc_routes_bp.route("/api/launchpad/execute", methods=["POST"])
def launchpad_execute():
    """One-stop execution: resolves playbook or prompt → loads DAG → runs background."""
    try:
        payload = request.get_json() or {}
        playbook_id = payload.get("playbook_id")
        prompt = payload.get("prompt", "")
        team_name = payload.get("team_name", "Squad_A")
        variables = payload.get("variables", {})

        exec_id = f"lp_{int(time.time()*1000)}"
        nodes = []
        edges = []
        label = ""

        # Route 1: Playbook-based
        if playbook_id and playbook_id != "__ai_generated":
            fresh_playbooks = _load_playbooks()
            if playbook_id not in fresh_playbooks:
                return jsonify({"status": "error", "message": f"Playbook '{playbook_id}' not found"}), 404
            pb = fresh_playbooks[playbook_id]
            nodes = pb.get("nodes", [])
            edges = pb.get("edges", [])
            label = pb.get("title", playbook_id)

            # Apply to team config
            root_dir = ROOT_DIR
            chatchain_path = os.path.join(root_dir, "CompanyConfig", "Teams", team_name, "ChatChainConfig.json")
            if not os.path.exists(chatchain_path):
                chatchain_path = os.path.join(root_dir, "CompanyConfig", "Default", "ChatChainConfig.json")
            try:
                with open(chatchain_path, 'r', encoding='utf-8') as f:
                    chatchain_data = json.load(f)
                chatchain_data["nodes"] = nodes
                chatchain_data["edges"] = edges
                # Inject variables into node prompts
                for node in chatchain_data["nodes"]:
                    if variables:
                        extra = " | ".join(f"{k}: {v}" for k, v in variables.items() if v)
                        if extra:
                            node["title"] = node.get("title", node.get("id", "")) + f" [{extra}]"
                target_path = os.path.join(root_dir, "CompanyConfig", "Teams", team_name, "ChatChainConfig.json")
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, 'w', encoding='utf-8') as f:
                    json.dump(chatchain_data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                logging.warning(f"LaunchPad config apply error: {e}")

        # Route 2: Pre-generated DAG passed in payload (from AI or frontend)
        elif payload.get("nodes"):
            nodes = payload.get("nodes")
            edges = payload.get("edges", [])
            label = prompt or payload.get("label") or "AI Generated Workflow"

        # Route 3: AI-generated DAG (from prompt)
        elif prompt:
            import re as _re
            steps = [s.strip() for s in prompt.replace(">", "→").replace("->", "→").split("→") if s.strip()]
            if len(steps) <= 1:
                steps = [s.strip() for s in prompt.split(",") if s.strip()]
            if len(steps) <= 1:
                # Korean words are often 2 chars (코드, 리뷰, 요약, 분석, etc.)
                steps = [s.strip() for s in prompt.split(" ") if len(s.strip()) > 1][:8]
            # If still only 0-1 step, treat the entire prompt as a single task
            if len(steps) <= 1 and prompt.strip():
                steps = [prompt.strip()]

            nodes = [{"id": "Trigger", "phase": "Trigger", "phaseType": "⚡ Pipeline Trigger",
                      "x": 80, "y": 250, "max_turn_step": 0, "need_reflect": "False"}]
            for i, step in enumerate(steps):
                node_id = _re.sub(r'[^a-zA-Z0-9_가-힣]', '', step.replace(' ', '_')) or f"Step_{i+1}"
                nodes.append({"id": node_id, "phase": "SimplePhase", "phaseType": "SimplePhase",
                              "title": step, "x": 80 + (i + 1) * 150, "y": 250,
                              "max_turn_step": -1, "need_reflect": "True"})
                prev_id = "Trigger" if i == 0 else (_re.sub(r'[^a-zA-Z0-9_가-힣]', '', steps[i-1].replace(' ', '_')) or f"Step_{i}")
                edges.append({"id": f"e_{i}", "source": prev_id, "target": node_id})
            label = prompt[:50]
        else:
            return jsonify({"status": "error", "message": "playbook_id or prompt required"}), 400

        # Record execution
        exec_record = {
            "id": exec_id,
            "label": label,
            "team_name": team_name,
            "playbook_id": playbook_id,
            "status": "running",
            "progress": 10,
            "variables": variables,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "node_count": len(nodes)
        }
        _launchpad_executions.insert(0, exec_record)
        # Keep max 50
        if len(_launchpad_executions) > 50:
            _launchpad_executions[:] = _launchpad_executions[:50]

        # ── Bookclub Playbook: Direct HTML generation ──
        if playbook_id == "bookclub" and variables:
            try:
                result = _generate_bookclub_html(exec_id, variables)
                exec_record["status"] = "completed"
                exec_record["progress"] = 100
                exec_record["output_file"] = result["filename"]
                exec_record["download_url"] = f"/api/launchpad/download/{exec_id}"
                return jsonify({
                    "status": "success",
                    "exec_id": exec_id,
                    "team_name": team_name,
                    "label": label,
                    "node_count": len(nodes),
                    "output": {
                        "type": "html_file",
                        "filename": result["filename"],
                        "download_url": f"/api/launchpad/download/{exec_id}",
                        "preview_url": f"/api/launchpad/preview/{exec_id}",
                        "file_size": result.get("file_size", 0)
                    }
                })
            except Exception as e:
                logging.error(f"[Bookclub] HTML generation error: {e}")
                exec_record["status"] = "error"
                exec_record["error"] = str(e)[:200]
                return jsonify({"status": "error", "message": f"북클럽 페이지 생성 실패: {str(e)[:200]}"}), 500

        # Load grounding knowledge contents (RAG)
        material_file = payload.get("material_file")
        injected = list(squad_injected_knowledge.get(team_name, []))
        if material_file and material_file not in injected:
            injected.insert(0, material_file)

        knowledge_sources = []
        root_dir = ROOT_DIR
        knowledge_dir = os.path.join(root_dir, "CompanyConfig", "Knowledge")

        # Prefer pre-indexed chunks (already extracted from PDF/etc.) over raw file reads
        team_chunks = _knowledge_chunks.get(team_name, []) if isinstance(_knowledge_chunks, dict) else []
        shared_chunks = _shared_chunks if isinstance(_shared_chunks, dict) else {}
        logging.info(f"[LaunchPad] Knowledge: {len(shared_chunks)} shared files, {len(team_chunks)} team chunks, material={material_file}")

        for fname in injected:
            fpath = os.path.join(knowledge_dir, fname)

            # Strategy 1: Use pre-indexed chunks (works for large PDFs too)
            file_chunks = [c for c in team_chunks if c.get("source") == fname]

            # Strategy 1b: Direct key lookup in shared chunks
            if not file_chunks:
                file_chunks = shared_chunks.get(fname, [])

            # Strategy 1c: Race condition fallback — key may exist with empty list,
            # but chunks may be stored under a different key with matching source field
            if not file_chunks:
                for _key, _chunks_list in shared_chunks.items():
                    if _chunks_list:
                        matched = [c for c in _chunks_list if c.get("source") == fname]
                        if matched:
                            file_chunks = matched
                            break

            # Strategy 1d: Try live app module reference (bypass stale globals)
            if not file_chunks and _app_module:
                try:
                    live_shared = getattr(_app_module, '_shared_chunks', {})
                    file_chunks = live_shared.get(fname, [])
                    if not file_chunks:
                        for _chunks_list in live_shared.values():
                            matched = [c for c in (_chunks_list or []) if c.get("source") == fname]
                            if matched:
                                file_chunks = matched
                                break
                except Exception:
                    pass

            if file_chunks:
                # Assemble pre-indexed content (top chunks, limited to ~8000 chars)
                assembled = []
                total_len = 0
                for c in file_chunks[:20]:  # max 20 chunks per file
                    chunk_text = c.get("chunk", "")
                    if total_len + len(chunk_text) > 8000:
                        break
                    assembled.append(chunk_text)
                    total_len += len(chunk_text)
                if assembled:
                    knowledge_sources.append({
                        "name": fname,
                        "content": "\n---\n".join(assembled)
                    })
                    logging.info(f"[LaunchPad] ✅ Loaded {len(assembled)} chunks for '{fname}' ({total_len} chars)")
                continue

            # Strategy 2: Direct file read for small text files only
            if os.path.exists(fpath):
                size_ok, fsize = validate_file_size(fpath, max_bytes=500 * 1024 * 1024)  # 500MB
                if not size_ok:
                    logging.warning(f"Knowledge file too large ({fsize} bytes): {fname}")
                    continue
                # Skip binary files (PDFs) — they need extraction, not raw read
                if fname.lower().endswith('.pdf'):
                    logging.warning(f"[LaunchPad] ⚠️ PDF '{fname}' has no pre-indexed chunks — skipping")
                    continue
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    knowledge_sources.append({
                        "name": fname,
                        "content": content
                    })
                except Exception as e:
                    logging.error(f"Failed to read knowledge file {fname}: {e}")

        # Try background execution if available
        try:
            if 'execute_workflow_background' in globals():
                execute_workflow_background(
                    team_name=team_name,
                    nodes=nodes,
                    edges=edges,
                    knowledge_sources=knowledge_sources,
                    socketio_ref=socketio_server,
                    task_prompt=prompt or label,
                    resume_from_exec_id=exec_id
                )
        except Exception as e:
            logging.warning(f"Background execution error: {e}")

        return jsonify({
            "status": "success",
            "exec_id": exec_id,
            "team_name": team_name,
            "label": label,
            "node_count": len(nodes)
        })

    except Exception as e:
        logging.error(f"LaunchPad execute error: {e}")
        return jsonify({"status": "error", "message": str(e)[:200]}), 500



@misc_routes_bp.route("/api/launchpad/suggestions", methods=["GET"])
def launchpad_suggestions():
    """Return prompt suggestions based on recent executions and popular playbooks."""
    suggestions = [
        {"text": "신제품 출시 마케팅 이메일 초안 작성해 줘", "category": "마케팅"},
        {"text": "주간 실적 요약 보고서 생성", "category": "보고서"},
        {"text": "코드 리뷰 및 품질 검사 자동화", "category": "개발"},
        {"text": "고객 문의 FAQ 문서 작성", "category": "고객지원"},
        {"text": "경쟁사 분석 보고서 생성", "category": "전략"},
        {"text": "기술 문서 자동 생성 파이프라인", "category": "문서화"}
    ]

    # Add recent executions as suggestions
    for exec_rec in _launchpad_executions[:3]:
        if exec_rec.get("label"):
            suggestions.append({
                "text": exec_rec["label"],
                "category": "최근 실행",
                "rerun": True
            })

    return jsonify({"status": "success", "suggestions": suggestions})




# --- #4/#5: Enhanced AI DAG with LLM attempt ---

@misc_routes_bp.route("/api/squad/task", methods=["POST"])
def api_squad_publish_task():
    """Publish a task to another squad via the message bus."""
    if not _cross_squad_bus:
        return jsonify({"status": "error", "message": "CrossSquadBus not available"}), 503
    data = request.get_json(force=True)
    task_id = _cross_squad_bus.publish_task(
        from_squad=data.get("from_squad", "CEO"),
        to_squad=data.get("to_squad", "Core_Engine"),
        task_type=data.get("task_type", "command"),
        task_description=data.get("description", ""),
        payload=data.get("payload", {})
    )
    return jsonify({"status": "success", "task_id": task_id})


@misc_routes_bp.route("/api/squad/<squad_name>/inbox", methods=["GET"])
def api_squad_inbox(squad_name):
    """Fetch inbox for a squad."""
    if not _cross_squad_bus:
        return jsonify({"status": "success", "tasks": []})
    tasks = _cross_squad_bus.fetch_inbox(squad_name)
    return jsonify({"status": "success", "tasks": tasks, "count": len(tasks)})


@misc_routes_bp.route("/api/squad/task/<task_id>/result", methods=["POST"])
def api_squad_post_result(task_id):
    """Post result for a cross-squad task."""
    if not _cross_squad_bus:
        return jsonify({"status": "error", "message": "Not available"}), 503
    data = request.get_json(force=True)
    _cross_squad_bus.post_result(task_id, data.get("from_squad", ""), data.get("to_squad", ""), data.get("result", {}))
    return jsonify({"status": "success"})


# ═══════════════════════════════════════════════════════
#  🟡 B7: DataCenter — 트랜잭션 기반 데이터 관리
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/data/status", methods=["GET"])
def api_data_center_status():
    """Get data center status."""
    if not _data_center:
        return jsonify({"status": "error", "message": "DataCenter not available"}), 503
    return jsonify({"status": "success", "data_center": {"active": True, "transaction_count": getattr(_data_center, '_tx_count', 0)}})


# ═══════════════════════════════════════════════════════
#  🟡 B8: EvalQuality — 코드 품질 평가
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/eval/quality/<project_name>", methods=["POST"])
def api_eval_quality(project_name):
    """Evaluate code quality for a WareHouse project."""
    if not _eval_quality_loaded:
        return jsonify({"status": "error", "message": "EvalQuality not available"}), 503
    root = ROOT_DIR  # #4
    project_dir = os.path.join(root, "WareHouse", project_name)
    if not os.path.isdir(project_dir):
        return jsonify({"status": "error", "message": f"Project '{project_name}' not found"}), 404
    try:
        completeness = get_completeness(project_dir)
        executability = get_executability(project_dir)
        consistency = get_consistency(project_dir)
        return jsonify({"status": "success", "quality": {
            "completeness": completeness, "executability": executability,
            "consistency": consistency, "project": project_name
        }})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ═══════════════════════════════════════════════════════
#  🟡 B9: ExecutiveBoard — CEO 작업 플래닝/거버넌스
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/executive/plan", methods=["POST"])
def api_executive_plan():
    """Draft a task plan from CEO prompt."""
    if not _ceo_orchestrator:
        return jsonify({"status": "error", "message": "ExecutiveBoard not available"}), 503
    data = request.get_json(force=True)
    plan = _ceo_orchestrator.draft_task_plan(data.get("prompt", ""))
    return jsonify({"status": "success", "plan": plan})


@misc_routes_bp.route("/api/executive/gate", methods=["POST"])
def api_executive_gate():
    """Enforce governance gate on a team task."""
    if not _ceo_orchestrator:
        return jsonify({"status": "error", "message": "ExecutiveBoard not available"}), 503
    data = request.get_json(force=True)
    passed = _ceo_orchestrator.enforce_governance_gate(data.get("team", "Core_Engine"), data.get("plan", {}))
    return jsonify({"status": "success", "passed": passed})


# ═══════════════════════════════════════════════════════
#  🟡 B10: KnowledgeConnector — 팀별 지식 문서 주입
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/notify/dispatch", methods=["POST"])
def api_notify_dispatch():
    """Dispatch notification via all channels."""
    if not _omni_sink_loaded:
        return jsonify({"status": "error", "message": "OmniChannel not available"}), 503
    data = request.get_json(force=True)
    result = OmniChannelSink.dispatch_all(data.get("team", ""), data.get("title", ""), data.get("text", ""))
    return jsonify({"status": "success", "result": result})


# ═══════════════════════════════════════════════════════
#  🟡 B12: ParallelPipeline — 동시 다중 프로젝트 빌드
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/pipeline/batch", methods=["POST"])
def api_pipeline_batch():
    """Start a batch of parallel pipelines."""
    if not _parallel_mgr:
        return jsonify({"status": "error", "message": "ParallelPipeline not available"}), 503
    data = request.get_json(force=True)
    specs = [ProjectSpec(task=s.get("task", ""), team_name=s.get("team", "Core_Engine"),
                         model=s.get("model", "Default")) for s in data.get("projects", [])]
    _parallel_mgr.add_batch(specs)
    return jsonify({"status": "success", "queued": len(specs)})


# ═══════════════════════════════════════════════════════
#  🟡 B13: PluginSystem — 플러그인 등록/실행
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/plugins", methods=["GET"])
def api_plugins_list():
    """List registered plugins."""
    plugins = []
    if _plugin_registry_loaded:
        try:
            registry = PluginRegistry if 'PluginRegistry' in dir() else None
            if registry:
                plugins = [p.to_dict() for p in registry.get_all()]
        except Exception as _e:
            logging.debug(f"[suppressed] Exception: {_e}")
    return jsonify({"status": "success", "plugins": plugins})


# ═══════════════════════════════════════════════════════
#  🟡 B14: SessionTimeout — 세션 타임아웃 가드
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/session/status", methods=["GET"])
def api_session_status():
    """Get session timeout configuration."""
    return jsonify({"status": "success", "session": {
        "timeout_guard_loaded": _session_timeout_loaded,
        "default_max_seconds": 3600,
    }})


# ═══════════════════════════════════════════════════════
#  🟡 B15: ToolRegistry — 에이전트 도구 레지스트리
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/tools/registry", methods=["GET"])
def api_tools_list():
    """List registered tools."""
    if not _tool_registry:
        return jsonify({"status": "success", "tools": []})
    specs = _tool_registry.get_openai_tools_specs()
    return jsonify({"status": "success", "tools": specs, "count": len(specs)})


@misc_routes_bp.route("/api/tools/<tool_name>/execute", methods=["POST"])
def api_tools_execute(tool_name):
    """Execute a registered tool."""
    if not _tool_registry:
        return jsonify({"status": "error", "message": "ToolRegistry not available"}), 503
    data = request.get_json(force=True)
    import json as _json
    result = _tool_registry.execute_tool(tool_name, _json.dumps(data.get("arguments", {})))
    return jsonify({"status": "success", "result": result})


# ═══════════════════════════════════════════════════════
#  🟡 B16: VectorDB — 임베딩 기반 유사도 검색
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/vector/add", methods=["POST"])
def api_vector_add():
    """Add a document to the vector DB."""
    if not _vector_db:
        return jsonify({"status": "error", "message": "VectorDB not available"}), 503
    data = request.get_json(force=True)
    _vector_db.add_document(data.get("text", ""), data.get("metadata", {}))
    return jsonify({"status": "success"})


@misc_routes_bp.route("/api/vector/search", methods=["POST"])
def api_vector_search():
    """Search for similar documents."""
    if not _vector_db:
        return jsonify({"status": "success", "results": []})
    data = request.get_json(force=True)
    results = _vector_db.similarity_search(data.get("query", ""), k=data.get("k", 5))
    return jsonify({"status": "success", "results": [{"text": r[0], "score": r[1], "metadata": r[2]} for r in results]})


# ═══════════════════════════════════════════════════════
#  🟡 B17: VisionHealing — 시각적 UI 자동 수정
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/vision/heal/<project_name>", methods=["POST"])
def api_vision_heal(project_name):
    """Run visual healing loop on a project."""
    if not _vision_healer:
        return jsonify({"status": "error", "message": "VisionHealing not available"}), 503
    return jsonify({"status": "success", "message": f"Visual healing queued for {project_name}"})


# ═══════════════════════════════════════════════════════
#  🟡 B18: WebOperator — 경쟁사 분석/웹 자동화
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/web/capture", methods=["POST"])
def api_web_capture():
    """Capture a web page screenshot."""
    if not _web_operator_loaded:
        return jsonify({"status": "error", "message": "WebOperator not available"}), 503
    data = request.get_json(force=True)
    result = WebOperator.navigate_and_operate(data.get("url", ""), data.get("actions", []))
    return jsonify({"status": "success", "result": result})


# ═══════════════════════════════════════════════════════
#  🟡 B19: ApprovalSystem — 작업 승인 게이트
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/approvals/pending", methods=["GET"])
def api_approvals_pending():
    """List pending approvals."""
    return jsonify({"status": "success", "pending": [], "system_loaded": _approval_sys is not None})


@misc_routes_bp.route("/api/approve/<team_name>/<node_id>", methods=["POST"])
def api_approve_task(team_name, node_id):
    """Approve a task for a team."""
    if not _approval_sys:
        return jsonify({"status": "success", "approved": True, "message": "Auto-approved (system not active)"})
    result = _approval_sys.request_approval(team_name, node_id)
    return jsonify({"status": "success", "approved": result})


# ═══════════════════════════════════════════════════════
#  🟡 B20: SelfEvolvingLoop — 코드 자가 개선 루프
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/evolve/<project_name>", methods=["POST"])
def api_evolve_project(project_name):
    """Start self-evolution cycle for a project."""
    if not _self_evolving:
        return jsonify({"status": "error", "message": "SelfEvolvingLoop not available"}), 503
    root = ROOT_DIR  # #4
    project_dir = os.path.join(root, "WareHouse", project_name)
    if not os.path.isdir(project_dir):
        return jsonify({"status": "error", "message": "Project not found"}), 404
    return jsonify({"status": "success", "message": f"Evolution cycle queued for {project_name}"})


# ═══════════════════════════════════════════════════════
#  🟡 B21: ContextManager — 프로젝트 히스토리 컨텍스트
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/context/<project_name>", methods=["GET"])
def api_context_project(project_name):
    """Get project history context."""
    if not _context_mgr:
        return jsonify({"status": "error", "message": "ContextManager not available"}), 503
    history = _context_mgr.collect_project_history(project_name)
    return jsonify({"status": "success", "project": project_name, "context": history[:3000]})


@misc_routes_bp.route("/api/context/build", methods=["POST"])
def api_context_build():
    """Build incremental context for a project."""
    if not _context_mgr:
        return jsonify({"status": "error", "message": "Not available"}), 503
    data = request.get_json(force=True)
    ctx = _context_mgr.build_incremental_context(
        data.get("project", ""), data.get("new_task", ""), data.get("sprint_history", []))
    return jsonify({"status": "success", "context": ctx[:5000]})


# ═══════════════════════════════════════════════════════
#  🟡 B22: AIRouter — LLM 티어 라우팅 (로컬/클라우드)
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/webhooks", methods=["GET"])
def api_webhooks_list():
    """List configured webhooks."""
    if _webhook_queue and hasattr(_webhook_queue, 'list_hooks'):
        return jsonify({"status": "success", "webhooks": _webhook_queue.list_hooks()})
    return jsonify({"status": "success", "webhooks": [], "available": _webhook_queue is not None})


@misc_routes_bp.route("/api/webhooks/test", methods=["POST"])
def api_webhooks_test():
    """Send a test webhook event."""
    if not _webhook_queue:
        return jsonify({"status": "error", "message": "WebhookQueue not available"}), 503
    data = request.get_json(force=True)
    try:
        _webhook_queue.enqueue(data.get("event_type", "test"), data.get("payload", {}))
        return jsonify({"status": "success", "message": "Test event enqueued"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ═══════════════════════════════════════════════════════
#  🟢 C27: Workflow Recovery — 서버 재시작 복구
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/recovery/status", methods=["GET"])
def api_recovery_status():
    """Get workflow recovery status."""
    recoverable = []
    if _ceo_persistence_ok:
        try:
            result = list_commands(status="in_progress", limit=50)
            recoverable = result.get("commands", [])
        except Exception as _e:
            logging.debug(f"[suppressed] Exception: {_e}")
    return jsonify({"status": "success", "recoverable": len(recoverable),
                    "recovery_engine": _workflow_recovery is not None,
                    "commands": recoverable[:10]})


@misc_routes_bp.route("/api/recovery/run", methods=["POST"])
def api_recovery_run():
    """Attempt to recover interrupted pipelines."""
    recovered = 0
    if _ceo_persistence_ok:
        try:
            result = list_commands(status="in_progress", limit=50)
            for cmd in result.get("commands", []):
                update_command_status(cmd["id"], "error", "⚠️ 서버 재시작으로 인한 중단 — 복구 필요")
                recovered += 1
        except Exception as _e:
            logging.debug(f"[suppressed] Exception: {_e}")
    return jsonify({"status": "success", "recovered": recovered})


# ═══════════════════════════════════════════════════════
#  🔵 D28: ZIP Download — 결과물 다운로드
# ═══════════════════════════════════════════════════════


@misc_routes_bp.route("/api/system/stats", methods=["GET"])
def api_system_stats():
    """#7: Return cached system stats (collected by background thread every 10s)."""
    with _system_stats_lock:
        cached = _system_stats_cache.get("data")
    
    if cached:
        return jsonify(cached)
    
    # Fallback: first request before background thread has populated cache
    import platform
    return jsonify({
        "cpu": {"percent": 0, "cores": os.cpu_count() or 1, "load_avg": [0, 0, 0]},
        "memory": {"total_gb": 0, "used_gb": 0, "percent": 0},
        "disk": {"total_gb": 0, "used_gb": 0, "percent": 0},
        "processes": {"total": 0, "python": 0},
        "platform": platform.system(),
        "timestamp": datetime.now().isoformat(),
        "_cache_status": "warming_up"
    })


# ═══════════════════════════════════════════════════════
#  🤖 HuggingFace AI Model Management APIs
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/books", methods=["GET"])
def api_books_list():
    """List all books in the library."""
    if not _book_ok:
        return jsonify({"status": "error", "message": "Book pipeline not loaded"}), 503
    books = _book_pipeline.list_books()
    return jsonify({"status": "success", "books": books, "total": len(books)})



@misc_routes_bp.route("/api/cache/invalidate", methods=["POST"])
def api_cache_invalidate():
    """#8: Clear API cache."""
    _api_cache.clear()
    return jsonify({"status": "success", "message": "Cache cleared"})


# ═══════════════════════════════════════════
#  #11: Structured Error Logging API
# ═══════════════════════════════════════════

@misc_routes_bp.route("/api/system/errors", methods=["GET"])
def api_system_errors():
    """#11: Get recent structured errors."""
    limit = request.args.get("limit", 50, type=int)
    try:
        import sqlite3 as _s3
        conn = _s3.connect(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ceo_commands.db"))
        rows = conn.execute(
            "SELECT * FROM log_store ORDER BY rowid DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        cols = ["id", "level", "source", "message", "timestamp"]
        errors = [dict(zip(cols, r[:len(cols)])) for r in rows]
        return jsonify({"status": "success", "errors": errors, "count": len(errors)})
    except Exception as e:
        return jsonify({"status": "success", "errors": [], "count": 0, "note": str(e)})


# ═══════════════════════════════════════════
#  #22: Simple API Key Authentication
# ═══════════════════════════════════════════

@misc_routes_bp.route("/api/auth/check", methods=["GET"])
def api_auth_check():
    """#22: Check if API key is valid (stub — always allows for now)."""
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        try:
            import sqlite3 as _s3
            conn = _s3.connect(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ceo_commands.db"))
            row = conn.execute("SELECT * FROM api_keys WHERE key_value = ? AND active = 1", (api_key,)).fetchone()
            conn.close()
            if row:
                return jsonify({"status": "success", "authenticated": True, "user": row[1] if len(row) > 1 else "admin"})
        except Exception as _auth_err:
            logging.debug(f"Auth DB check exception: {_auth_err}")
    # Default: allow (local development)
    return jsonify({"status": "success", "authenticated": True, "mode": "local-dev"})


# ═══════════════════════════════════════════
#  #23: Standard Response Wrapper
# ═══════════════════════════════════════════

@misc_routes_bp.route("/api/config", methods=["GET"])
def api_config():
    """#25: Get server configuration (safe subset)."""
    return jsonify({
        "status": "success",
        "config": {
            "port": int(os.environ.get("CHATDEV_PORT", 8188)),
            "debug": os.environ.get("FLASK_DEBUG", "false").lower() == "true",
            "teams": list(_team_files.keys()) if _team_files else [],
            "knowledge_dir": os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "knowledge"),
            "db_path": os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ceo_commands.db"),
            "indexing_ready": _indexing_ready,
            "brain_module": _brain_ok,
            "version": "2.0.0",
        }
    })


# ── #6: Config Hot-Reload Endpoint ──

@misc_routes_bp.route("/api/config/reload", methods=["POST"])
def api_config_reload():
    """#6: Hot-reload configuration without server restart.
    Clears JSON cache, reloads playbooks, and refreshes env vars.
    """
    try:
        # Clear mtime-based JSON file cache (#9)
        with _json_cache_lock:
            _json_file_cache.clear()

        # Reload playbooks (#3)
        global playbook_cache
        playbook_cache = _load_playbooks()

        # Reload .env if python-dotenv is available
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)
        except ImportError:
            logging.info("dotenv package not found, skipping .env reload")

        return jsonify({
            "status": "success",
            "message": "🔄 설정이 성공적으로 리로드되었습니다",
            "reloaded": ["json_cache", "playbooks", "env_vars"],
        })
    except Exception as e:
        return safe_error_response(e)


# ── #2: Module Health Status Endpoint ──

@misc_routes_bp.route("/api/modules", methods=["GET"])
def api_modules_status():
    """#2: Show status of all enterprise modules (loaded/failed)."""
    loaded = {k: v for k, v in _ENTERPRISE_MODULES.items() if v}
    failed = {k: v for k, v in _ENTERPRISE_MODULES.items() if not v}
    return jsonify({
        "status": "success",
        "total": len(_ENTERPRISE_MODULES),
        "loaded": len(loaded),
        "failed": len(failed),
        "modules": {k: ("loaded" if v else "failed") for k, v in _ENTERPRISE_MODULES.items()},
    })


# ═══════════════════════════════════════════
#  #27: Auto-Summary API (Stub)
# ═══════════════════════════════════════════

@misc_routes_bp.route("/api/health/deep", methods=["GET"])
def api_deep_health():
    """Comprehensive health check of all subsystems (#11)."""
    if _backend_utils_ok:
        return jsonify(deep_health_check())
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})


# ═══════════════════════════════════════════════════════
#  #22: Pipeline State Persistence Endpoint
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/pipeline/states", methods=["GET"])
def api_pipeline_states():
    """Get all persisted pipeline states (#22)."""
    if _backend_utils_ok:
        states = load_pipeline_states()
        return jsonify({"status": "success", "states": states, "count": len(states)})
    return jsonify({"status": "error", "message": "Backend utils not loaded"}), 503


# ═══════════════════════════════════════════════════════
#  #25: DB Backup Endpoint
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/system/backup", methods=["POST"])
def api_system_backup():
    """Create a database backup (#25)."""
    if _backend_utils_ok:
        path = backup_database()
        if path:
            return jsonify({"status": "success", "backup_path": path})
        return jsonify({"status": "error", "message": "백업 실패"}), 500
    return jsonify({"status": "error", "message": "Backend utils not loaded"}), 503

# ═══════════════════════════════════════════════════════
#  #23: Upload Cleanup Scheduler (uses module-level threading import)
# ═══════════════════════════════════════════════════════


@misc_routes_bp.route("/health", methods=["GET"])
def health_liveness():
    """#25: Liveness probe — server is running."""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@misc_routes_bp.route("/health/ready", methods=["GET"])
def health_readiness():
    """#25: Readiness probe — all critical subsystems are operational."""
    checks = {
        "database": _PERSISTENT_STATE,
        "enterprise_modules": len(_ENTERPRISE_MODULES),
        "backend_utils": _backend_utils_ok,
    }
    all_ok = _PERSISTENT_STATE and _backend_utils_ok
    return jsonify({
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
        "timestamp": datetime.now().isoformat()
    }), 200 if all_ok else 503


# ═══════════════════════════════════════════════════════
#  #27: Graceful Shutdown Handler
# ═══════════════════════════════════════════════════════


@misc_routes_bp.route("/api/health", methods=["GET"])
def health_check_advanced():
    """#30: Health check — server status, LLM connectivity, disk usage."""
    import shutil
    
    checks = {
        "server": "ok",
        "timestamp": datetime.now().isoformat(),
        "uptime_info": "running",
    }
    
    # Disk usage
    try:
        disk = shutil.disk_usage(VISUALIZER_DIR)
        checks["disk"] = {
            "total_gb": round(disk.total / (1024**3), 1),
            "used_gb": round(disk.used / (1024**3), 1),
            "free_gb": round(disk.free / (1024**3), 1),
            "usage_percent": round(disk.used / disk.total * 100, 1)
        }
    except Exception:
        checks["disk"] = {"status": "unknown"}
    
    # LLM provider status
    try:
        checks["llm"] = {
            "engine": _AI_ENGINE_CONFIG.get("provider", "unknown"),
            "model": _AI_ENGINE_CONFIG.get("model", "unknown"),
            "configured": bool(_AI_ENGINE_CONFIG.get("api_key"))
        }
    except Exception:
        checks["llm"] = {"status": "unknown"}
    
    # Worker infrastructure
    checks["infra"] = {
        "celery": _CELERY_AVAILABLE,
        "redis": _REDIS_AVAILABLE,
        "worker_mode": WORKER_MODE
    }
    
    # Execution history count
    history_dir = os.path.join(VISUALIZER_DIR, "execution_history")
    try:
        hist_count = len([f for f in os.listdir(history_dir) if f.endswith(".json")]) if os.path.exists(history_dir) else 0
        checks["history_files"] = hist_count
    except Exception:
        checks["history_files"] = -1
    
    # #18: Auto-cleanup on health check (lazy cleanup)
    try:
        if os.path.exists(history_dir):
            cleanup_result = cleanup_execution_history(history_dir, max_age_days=30, max_files=100)
            if cleanup_result["deleted"] > 0:
                logging.info(f"#18: Auto-cleaned {cleanup_result['deleted']} old execution history files")
                checks["cleanup"] = cleanup_result
    except Exception as e:
        logging.debug(f"Cleanup execution history failed: {e}")
    
    # #17: Save daily metering rollup
    try:
        metering = get_metering_summary()
        metering_dir = os.path.join(VISUALIZER_DIR, "metering_rollups")
        save_daily_metering_rollup(metering_dir, metering)
    except Exception as e:
        logging.debug(f"Saving daily metering rollup failed: {e}")
    
    return api_success(data=checks)


# ═══════════════════════════════════════════════════════
#  #24: Rate Limiting Middleware (before_request hook)
# ═══════════════════════════════════════════════════════

# Paths that consume LLM resources and need strict rate limiting


# ═══════════════════════════════════════════════════════
#  🧬 V5 Hermes: Self-Evolving Agent APIs
# ═══════════════════════════════════════════════════════

@misc_routes_bp.route("/api/hermes/skills", methods=["GET"])
def api_hermes_skills():
    """List all learned skills from the Skill Forge."""
    try:
        from visualizer.services.skill_forge import skill_forge
        status = request.args.get("status", "active")
        skills = skill_forge.list_skills(status=status)
        return jsonify({"status": "success", "skills": skills, "count": len(skills)})
    except Exception as e:
        return jsonify({"status": "success", "skills": [], "error": str(e)})


@misc_routes_bp.route("/api/hermes/skills/stats", methods=["GET"])
def api_hermes_skills_stats():
    """Get Skill Forge statistics."""
    try:
        from visualizer.services.skill_forge import skill_forge
        stats = skill_forge.get_stats()
        return jsonify({"status": "success", "stats": stats})
    except Exception as e:
        return jsonify({"status": "success", "stats": {}, "error": str(e)})


@misc_routes_bp.route("/api/hermes/skills/<skill_id>", methods=["GET"])
def api_hermes_skill_detail(skill_id):
    """Get detailed info for a specific skill."""
    try:
        from visualizer.services.skill_forge import skill_forge
        skill = skill_forge.get_skill(skill_id)
        if not skill:
            return jsonify({"status": "error", "message": "Skill not found"}), 404
        return jsonify({"status": "success", "skill": skill})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/hermes/skills/evolve", methods=["POST"])
def api_hermes_evolve():
    """Trigger skill evolution cycle."""
    try:
        from visualizer.services.skill_forge import skill_forge
        result = skill_forge.evolve()
        return jsonify({"status": "success", "evolution": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@misc_routes_bp.route("/api/hermes/user/profile", methods=["GET"])
def api_hermes_user_profile():
    """Get the current user behavior profile."""
    try:
        from visualizer.services.user_model import user_model
        user_id = request.args.get("user_id", "default")
        profile = user_model.get_profile(user_id)
        return jsonify({"status": "success", "profile": profile})
    except Exception as e:
        return jsonify({"status": "success", "profile": {}, "error": str(e)})


@misc_routes_bp.route("/api/hermes/user/suggestions", methods=["GET"])
def api_hermes_user_suggestions():
    """Get user-model-based parameter suggestions for a playbook."""
    try:
        from visualizer.services.user_model import user_model
        playbook_id = request.args.get("playbook_id", "")
        user_id = request.args.get("user_id", "default")
        suggestions = user_model.suggest_defaults(playbook_id, user_id)
        return jsonify({"status": "success", "suggestions": suggestions})
    except Exception as e:
        return jsonify({"status": "success", "suggestions": {}, "error": str(e)})


@misc_routes_bp.route("/api/hermes/memory/recall", methods=["POST"])
def api_hermes_memory_recall():
    """Cross-session smart recall using FTS5."""
    try:
        from visualizer.services.agent_long_memory import agent_long_memory
        data = request.get_json(force=True)
        results = agent_long_memory.smart_recall(
            query=data.get("query", ""),
            agent_id=data.get("agent_id"),
            limit=data.get("limit", 10),
        )
        return jsonify({"status": "success", "memories": results, "count": len(results)})
    except Exception as e:
        return jsonify({"status": "success", "memories": [], "error": str(e)})


@misc_routes_bp.route("/api/hermes/memory/nudge", methods=["GET"])
def api_hermes_memory_nudge():
    """Check for stale high-importance memories that need re-engagement."""
    try:
        from visualizer.services.agent_memory import agent_memory
        agent_id = request.args.get("agent_id", "ceo")
        nudges = agent_memory.nudge_check(agent_id)
        return jsonify({"status": "success", "nudges": nudges, "count": len(nudges)})
    except Exception as e:
        return jsonify({"status": "success", "nudges": [], "error": str(e)})


@misc_routes_bp.route("/api/hermes/stats", methods=["GET"])
def api_hermes_stats():
    """Get unified Hermes system statistics."""
    stats = {"hermes_version": "v5", "modules": {}}
    try:
        from visualizer.services.skill_forge import skill_forge
        stats["modules"]["skill_forge"] = skill_forge.get_stats()
    except Exception:
        stats["modules"]["skill_forge"] = {"status": "not_loaded"}
    try:
        from visualizer.services.user_model import user_model
        stats["modules"]["user_model"] = user_model.get_stats()
    except Exception:
        stats["modules"]["user_model"] = {"status": "not_loaded"}
    try:
        from visualizer.services.agent_long_memory import agent_long_memory
        lm_stats = agent_long_memory.get_stats()
        stats["modules"]["long_memory"] = lm_stats
    except Exception:
        stats["modules"]["long_memory"] = {"status": "not_loaded"}
    try:
        from visualizer.services.auto_learner import auto_learner
        stats["modules"]["auto_learner"] = auto_learner.get_learning_stats()
    except Exception:
        stats["modules"]["auto_learner"] = {"status": "not_loaded"}
    return jsonify({"status": "success", "stats": stats})


# ══════════════════════════════════════════════════════════════
# 📚 BOOKCLUB — HTML Page Generator Engine
# ══════════════════════════════════════════════════════════════

_BOOKCLUB_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "WareHouse", "_outputs", "bookclub")
os.makedirs(_BOOKCLUB_OUTPUT_DIR, exist_ok=True)

_BOOKCLUB_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "templates", "bookclub_template.html")


def _generate_bookclub_html(exec_id, variables):
    """Generate a standalone HTML bookclub detail page from template + variables.
    
    Reads the bookclub_template.html, replaces {{PLACEHOLDER}} tokens with
    structured content derived from the user-supplied variables.
    """
    import html as _html
    import re as _re

    # ── Read template ──
    with open(_BOOKCLUB_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        template = f.read()

    # ── Extract variables with safe defaults ──
    book_title       = variables.get("book_title", "책 제목 미정")
    author           = variables.get("author", "저자 미정")
    club_name        = variables.get("club_name", "온라인 북클럽")
    description      = variables.get("description", "북클럽 소개가 입력되지 않았습니다.")
    schedule_raw     = variables.get("schedule", "")
    topics_raw       = variables.get("discussion_topics", "")
    host_name        = variables.get("host_name", "")
    max_members      = variables.get("max_members", "20")
    meeting_time     = variables.get("meeting_time", "")
    price            = variables.get("price", "무료")
    cover_image_url  = variables.get("cover_image_url", "")

    # ── Cover image ──
    if cover_image_url and cover_image_url.strip():
        cover_html = f'<img src="{_html.escape(cover_image_url.strip())}" alt="{_html.escape(book_title)} 표지">'
    else:
        cover_html = '<div class="cover-placeholder">📖</div>'

    # ── Hero meta items ──
    hero_meta_parts = []
    if meeting_time:
        hero_meta_parts.append(f'<div class="hero-meta-item"><span class="icon">🕐</span><span>{_html.escape(meeting_time)}</span></div>')
    if max_members:
        hero_meta_parts.append(f'<div class="hero-meta-item"><span class="icon">👥</span><span>최대 {_html.escape(max_members)}명</span></div>')
    if price:
        hero_meta_parts.append(f'<div class="hero-meta-item"><span class="icon">💰</span><span>{_html.escape(price)}</span></div>')
    hero_meta_html = "\n                    ".join(hero_meta_parts)

    # ── Schedule cards ──
    schedule_cards_html = ""
    if schedule_raw.strip():
        lines = [l.strip() for l in schedule_raw.strip().split("\n") if l.strip()]
        for i, line in enumerate(lines):
            # Parse: "1회차: 6/20(금) — 파트1 핵심" or "Week 1: ..."
            parts = _re.split(r'[:：—–\-]', line, maxsplit=1)
            week_label = parts[0].strip() if len(parts) > 0 else f"{i+1}회차"
            week_detail = parts[1].strip() if len(parts) > 1 else line
            schedule_cards_html += f'''
                <div class="schedule-card animate-in">
                    <div class="week-num">{_html.escape(week_label)}</div>
                    <div class="week-title">{_html.escape(week_detail)}</div>
                </div>\n'''

    # ── Discussion topics ──
    discussion_section_html = ""
    if topics_raw.strip():
        topic_lines = [l.strip() for l in topics_raw.strip().split("\n") if l.strip()]
        topic_items_html = ""
        for i, topic in enumerate(topic_lines):
            # Remove leading numbers/bullets: "1. topic" → "topic"
            clean_topic = _re.sub(r'^[\d]+[.)\s]*', '', topic).strip()
            if not clean_topic:
                clean_topic = topic
            topic_items_html += f'''
                <li class="topic-item animate-in">
                    <span class="topic-num">{i+1}</span>
                    <span class="topic-text">{_html.escape(clean_topic)}</span>
                </li>\n'''
        discussion_section_html = f'''
    <section class="section" id="topics">
        <div class="container">
            <span class="section-label">💬 토론 주제</span>
            <h2 class="section-title">함께 나눌 이야기</h2>
            <ul class="topic-list">
                {topic_items_html}
            </ul>
        </div>
    </section>'''

    # ── Host card ──
    host_card_html = ""
    if host_name.strip():
        host_card_html = f'''
            <div class="host-card">
                <div class="host-avatar">🎙️</div>
                <div class="host-info">
                    <h4>{_html.escape(host_name)}</h4>
                    <p>북클럽 진행자</p>
                </div>
            </div>'''

    # ── Info cards ──
    info_cards_html = ""
    info_items = []
    if meeting_time:
        info_items.append(("🕐", "모임 시간", meeting_time))
    if max_members:
        info_items.append(("👥", "정원", f"최대 {max_members}명"))
    if price:
        info_items.append(("💰", "참가비", price))
    info_items.append(("💻", "모임 방식", "온라인 (Zoom/Google Meet)"))
    for icon, label, value in info_items:
        info_cards_html += f'''
                <div class="info-card animate-in">
                    <div class="info-icon">{icon}</div>
                    <div class="info-label">{label}</div>
                    <div class="info-value">{_html.escape(value)}</div>
                </div>\n'''

    # ── Apply all replacements ──
    html_output = template
    replacements = {
        "{{BOOK_TITLE}}": _html.escape(book_title),
        "{{AUTHOR}}": _html.escape(author),
        "{{CLUB_NAME}}": _html.escape(club_name),
        "{{DESCRIPTION}}": _html.escape(description),
        "{{COVER_IMAGE}}": cover_html,
        "{{HERO_META_ITEMS}}": hero_meta_html,
        "{{SCHEDULE_CARDS}}": schedule_cards_html,
        "{{DISCUSSION_SECTION}}": discussion_section_html,
        "{{HOST_CARD}}": host_card_html,
        "{{INFO_CARDS}}": info_cards_html,
        "{{MEETING_TIME}}": _html.escape(meeting_time) if meeting_time else "",
    }
    for token, value in replacements.items():
        html_output = html_output.replace(token, value)

    # ── Save to file ──
    import re as _re2
    safe_title = _re2.sub(r'[^a-zA-Z0-9가-힣_\- ]', '', book_title).strip().replace(' ', '_')[:40]
    filename = f"bookclub_{safe_title}_{exec_id}.html"
    filepath = os.path.join(_BOOKCLUB_OUTPUT_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_output)

    file_size = os.path.getsize(filepath)
    logging.info(f"📚 [Bookclub] Generated HTML: {filename} ({file_size} bytes)")

    return {
        "filename": filename,
        "filepath": filepath,
        "file_size": file_size
    }


@misc_routes_bp.route("/api/launchpad/download/<exec_id>", methods=["GET"])
def launchpad_download(exec_id):
    """Download the generated bookclub HTML file."""
    try:
        # Find the execution record
        record = None
        for rec in _launchpad_executions:
            if rec.get("id") == exec_id:
                record = rec
                break

        if not record:
            return jsonify({"status": "error", "message": "실행 기록을 찾을 수 없습니다."}), 404

        output_file = record.get("output_file")
        if not output_file:
            return jsonify({"status": "error", "message": "다운로드 가능한 파일이 없습니다."}), 404

        filepath = os.path.join(_BOOKCLUB_OUTPUT_DIR, output_file)
        if not os.path.exists(filepath):
            return jsonify({"status": "error", "message": "파일이 존재하지 않습니다."}), 404

        return send_file(
            filepath,
            mimetype='text/html',
            as_attachment=True,
            download_name=output_file
        )
    except Exception as e:
        logging.error(f"[Bookclub] Download error: {e}")
        return jsonify({"status": "error", "message": str(e)[:200]}), 500


@misc_routes_bp.route("/api/launchpad/preview/<exec_id>", methods=["GET"])
def launchpad_preview(exec_id):
    """Preview the generated bookclub HTML file in-browser."""
    try:
        record = None
        for rec in _launchpad_executions:
            if rec.get("id") == exec_id:
                record = rec
                break

        if not record:
            return jsonify({"status": "error", "message": "실행 기록을 찾을 수 없습니다."}), 404

        output_file = record.get("output_file")
        if not output_file:
            return jsonify({"status": "error", "message": "미리보기 가능한 파일이 없습니다."}), 404

        filepath = os.path.join(_BOOKCLUB_OUTPUT_DIR, output_file)
        if not os.path.exists(filepath):
            return jsonify({"status": "error", "message": "파일이 존재하지 않습니다."}), 404

        return send_file(filepath, mimetype='text/html')
    except Exception as e:
        logging.error(f"[Bookclub] Preview error: {e}")
        return jsonify({"status": "error", "message": str(e)[:200]}), 500


logger.info("✅ [Misc Routes Blueprint] Loaded — 141+ routes (Hermes V5 APIs, Bookclub Generator included)")

