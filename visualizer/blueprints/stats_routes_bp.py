# ══════════════════════════════════════════════════════════════
#   stats_routes_bp.py — Stats, System & Monitoring Routes (C-1 Split)
#   Extracted from misc_routes_bp.py for modular architecture
#   Routes: /api/infra/*, /api/logs/*, /api/system/*, /api/health/*,
#           /api/modules, /api/auth/check, /api/hermes/*
# ══════════════════════════════════════════════════════════════

import os
import re
import json
import time
import logging
import threading
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, send_from_directory, send_file, redirect, g

logger = logging.getLogger("chatdev.bp.stats")

stats_bp = Blueprint("stats", __name__)

# ── App.py shared state access ──
_app_module = None

_REQUIRED_APP_NAMES = [
    'ROOT_DIR', 'TEAMS_DIR', 'COMPANY_CONFIG_DIR', 'VISUALIZER_DIR',
    'squad_stats', 'squad_injected_knowledge',
    'validate_team_name', 'get_team_lock', 'lazy_import',
    'api_error', 'api_success', 'safe_error_response',
    'mcp_hub', 'secure_vault',
    # BUG-1 fix: previously missing variables that caused NameError
    'WORKER_MODE', '_CELERY_AVAILABLE', '_REDIS_AVAILABLE',
    '_ENTERPRISE_MODULES', '_backend_utils_ok', '_PERSISTENT_STATE',
    '_system_stats_lock', '_system_stats_cache', '_api_cache',
    '_AI_ENGINE_CONFIG', '_book_pipeline', '_book_ok',
    'get_logs', 'get_metering_summary', 'save_daily_metering_rollup',
    'deep_health_check', 'backup_database', 'load_pipeline_states',
    'cleanup_execution_history',
]

# ── Safe fallback defaults (used before app globals are loaded) ──
ROOT_DIR = None
TEAMS_DIR = None
COMPANY_CONFIG_DIR = None
VISUALIZER_DIR = None
squad_stats = {}
squad_injected_knowledge = {}
WORKER_MODE = "single"
_CELERY_AVAILABLE = False
_REDIS_AVAILABLE = False
_ENTERPRISE_MODULES = {}
_backend_utils_ok = False
_PERSISTENT_STATE = {}
_system_stats_lock = threading.Lock()
_system_stats_cache = {}
_api_cache = {}
_AI_ENGINE_CONFIG = {}
_book_pipeline = None
_book_ok = False

# ── Fallback function stubs (overridden by app globals when loaded) ──
def get_logs(limit=50, since=None): return []
def get_metering_summary(): return {"total_cost_usd": 0, "total_actions": 0, "total_tokens": 0}
def save_daily_metering_rollup(): pass
def deep_health_check(): return {"status": "unknown", "message": "App globals not loaded"}
def backup_database(*a, **kw): return {"status": "error", "message": "Not available"}
def load_pipeline_states(): return {}
def cleanup_execution_history(*a, **kw): return 0

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

@stats_bp.before_app_request
def _lazy_reload_stats_globals():
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


@stats_bp.route("/api/infra/status", methods=["GET"])
def infra_status():
    """Return infrastructure availability status."""
    return api_success(data={
        "worker_mode": WORKER_MODE,
        "celery": _CELERY_AVAILABLE,
        "redis": _REDIS_AVAILABLE,
    })


@stats_bp.route("/api/logs/live", methods=["GET"])
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

@stats_bp.route("/api/system/stats", methods=["GET"])
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

@stats_bp.route("/api/books", methods=["GET"])
def api_books_list():
    """List all books in the library."""
    if not _book_ok:
        return jsonify({"status": "error", "message": "Book pipeline not loaded"}), 503
    books = _book_pipeline.list_books()
    return jsonify({"status": "success", "books": books, "total": len(books)})



@stats_bp.route("/api/cache/invalidate", methods=["POST"])
def api_cache_invalidate():
    """#8: Clear API cache."""
    _api_cache.clear()
    return jsonify({"status": "success", "message": "Cache cleared"})


# ═══════════════════════════════════════════
#  #11: Structured Error Logging API
# ═══════════════════════════════════════════

@stats_bp.route("/api/system/errors", methods=["GET"])
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

@stats_bp.route("/api/auth/check", methods=["GET"])
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

@stats_bp.route("/api/modules", methods=["GET"])
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

@stats_bp.route("/api/health/deep", methods=["GET"])
def api_deep_health():
    """Comprehensive health check of all subsystems (#11)."""
    if _backend_utils_ok:
        return jsonify(deep_health_check())
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})


# ═══════════════════════════════════════════════════════
#  #22: Pipeline State Persistence Endpoint
# ═══════════════════════════════════════════════════════

@stats_bp.route("/api/pipeline/states", methods=["GET"])
def api_pipeline_states():
    """Get all persisted pipeline states (#22)."""
    if _backend_utils_ok:
        states = load_pipeline_states()
        return jsonify({"status": "success", "states": states, "count": len(states)})
    return jsonify({"status": "error", "message": "Backend utils not loaded"}), 503


# ═══════════════════════════════════════════════════════
#  #25: DB Backup Endpoint
# ═══════════════════════════════════════════════════════

@stats_bp.route("/api/system/backup", methods=["POST"])
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


@stats_bp.route("/health", methods=["GET"])
def health_liveness():
    """#25: Liveness probe — server is running."""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@stats_bp.route("/health/ready", methods=["GET"])
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


@stats_bp.route("/api/health", methods=["GET"])
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

@stats_bp.route("/api/hermes/skills", methods=["GET"])
def api_hermes_skills():
    """List all learned skills from the Skill Forge."""
    try:
        from visualizer.services.skill_forge import skill_forge
        status = request.args.get("status", "active")
        skills = skill_forge.list_skills(status=status)
        return jsonify({"status": "success", "skills": skills, "count": len(skills)})
    except Exception as e:
        return jsonify({"status": "success", "skills": [], "error": str(e)})


@stats_bp.route("/api/hermes/skills/stats", methods=["GET"])
def api_hermes_skills_stats():
    """Get Skill Forge statistics."""
    try:
        from visualizer.services.skill_forge import skill_forge
        stats = skill_forge.get_stats()
        return jsonify({"status": "success", "stats": stats})
    except Exception as e:
        return jsonify({"status": "success", "stats": {}, "error": str(e)})


@stats_bp.route("/api/hermes/skills/<skill_id>", methods=["GET"])
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


@stats_bp.route("/api/hermes/skills/evolve", methods=["POST"])
def api_hermes_evolve():
    """Trigger skill evolution cycle."""
    try:
        from visualizer.services.skill_forge import skill_forge
        result = skill_forge.evolve()
        return jsonify({"status": "success", "evolution": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@stats_bp.route("/api/hermes/user/profile", methods=["GET"])
def api_hermes_user_profile():
    """Get the current user behavior profile."""
    try:
        from visualizer.services.user_model import user_model
        user_id = request.args.get("user_id", "default")
        profile = user_model.get_profile(user_id)
        return jsonify({"status": "success", "profile": profile})
    except Exception as e:
        return jsonify({"status": "success", "profile": {}, "error": str(e)})


@stats_bp.route("/api/hermes/user/suggestions", methods=["GET"])
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


@stats_bp.route("/api/hermes/memory/recall", methods=["POST"])
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


@stats_bp.route("/api/hermes/memory/nudge", methods=["GET"])
def api_hermes_memory_nudge():
    """Check for stale high-importance memories that need re-engagement."""
    try:
        from visualizer.services.agent_memory import agent_memory
        agent_id = request.args.get("agent_id", "ceo")
        nudges = agent_memory.nudge_check(agent_id)
        return jsonify({"status": "success", "nudges": nudges, "count": len(nudges)})
    except Exception as e:
        return jsonify({"status": "success", "nudges": [], "error": str(e)})


@stats_bp.route("/api/hermes/stats", methods=["GET"])
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


