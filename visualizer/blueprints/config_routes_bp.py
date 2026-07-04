# ══════════════════════════════════════════════════════════════
#   config_routes_bp.py — Config & Integration Routes (C-1 Split)
#   Extracted from misc_routes_bp.py for modular architecture
#   Routes: /api/vault/*, /api/pipeline_config/*, /api/integrations/*,
#           /api/connectors/*, /api/config, /api/config/reload
# ══════════════════════════════════════════════════════════════

import os
import re
import json
import glob
import time
import logging
import threading
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, send_from_directory, send_file, redirect, g

logger = logging.getLogger("chatdev.bp.config")

config_bp = Blueprint("config", __name__)

# ── App.py shared state access ──
_app_module = None

_REQUIRED_APP_NAMES = [
    'ROOT_DIR', 'TEAMS_DIR', 'COMPANY_CONFIG_DIR', 'VISUALIZER_DIR',
    'squad_stats', 'squad_injected_knowledge',
    'validate_team_name', 'get_team_lock', 'lazy_import',
    'api_error', 'api_success', 'safe_error_response',
    'mcp_hub', 'secure_vault',
    # BUG-2 fix: previously missing variables
    '_ENTERPRISE_MODULES', '_team_files', '_indexing_ready', '_brain_ok',
    '_json_cache_lock', '_json_file_cache', 'playbook_cache', '_load_playbooks',
]

# ── Safe fallback defaults ──
ROOT_DIR = None
TEAMS_DIR = None
COMPANY_CONFIG_DIR = None
VISUALIZER_DIR = None
squad_stats = {}
squad_injected_knowledge = {}
_ENTERPRISE_MODULES = {}
_team_files = {}
_indexing_ready = False
_brain_ok = False
_json_cache_lock = threading.Lock()
_json_file_cache = {}
playbook_cache = {}
def _load_playbooks(): return {}
def lazy_import(mod, attr=None): return None
try:
    from visualizer.core.api_utils import safe_error_response, api_success, api_error
except ImportError:
    def safe_error_response(e, **kw): return jsonify({"status": "error", "message": str(e)}), 500
    def api_success(data=None, message="", **extra): return jsonify({"status": "success", "data": data, "message": message, **extra})
    def api_error(message="오류가 발생했습니다", status_code=400, **extra): return jsonify({"status": "error", "message": message, **extra}), status_code
secure_vault = None
mcp_hub = None

_app_globals_ready = False

def _import_app_globals_safe():
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
    for _name, _val in _ag.items():
        globals()[_name] = _val
except Exception as _e:
    logger.warning(f"Failed to import app globals: {_e}")

@config_bp.before_app_request
def _lazy_reload_config_globals():
    global _app_globals_ready
    if _app_globals_ready:
        return
    try:
        _ag2 = _import_app_globals_safe()
        for _name, _val in _ag2.items():
            globals()[_name] = _val
        _app_globals_ready = True
    except Exception:
        pass


@config_bp.route("/api/vault/status", methods=["GET"])
def api_vault_status():
    """Get status of all integration keys (masked, never plaintext)."""
    if not secure_vault:
        return jsonify({"status": "error", "message": "Vault not available"}), 500
    statuses = secure_vault.get_all_status()
    return jsonify({"status": "success", "integrations": statuses})



@config_bp.route("/api/vault/store", methods=["POST"])
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



@config_bp.route("/api/vault/test", methods=["POST"])
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



@config_bp.route("/api/vault/delete", methods=["POST"])
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


@config_bp.route("/api/pipeline_config/save", methods=["POST"])
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



@config_bp.route("/api/pipeline_config/load", methods=["GET"])
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

@config_bp.route("/api/integrations", methods=["GET"])
def list_integrations():
    """List all supported services and their connection status."""
    try:
        list_services = lazy_import('chatdev.integration_store', 'list_services')  # #5
        services = list_services()
        return jsonify({"status": "success", "services": services})
    except Exception as e:
        logging.error(f"[Integrations] List error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



@config_bp.route("/api/integrations", methods=["POST"])
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



@config_bp.route("/api/integrations/<service>", methods=["DELETE"])
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



@config_bp.route("/api/integrations/<service>/test", methods=["POST"])
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

@config_bp.route("/api/connectors/validate", methods=["POST"])
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

@config_bp.route("/api/backup_workflow", methods=["POST"])
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



@config_bp.route("/api/config", methods=["GET"])
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

@config_bp.route("/api/config/reload", methods=["POST"])
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

@config_bp.route("/api/modules", methods=["GET"])
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
