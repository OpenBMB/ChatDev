# ══════════════════════════════════════════════════════════════
#  Blueprint Registration Hub
#  Registers all domain-specific route blueprints with the Flask app.
#  Each blueprint file was auto-extracted from the monolithic app.py.
# ══════════════════════════════════════════════════════════════

from flask import Blueprint, jsonify
import logging

logger = logging.getLogger("chatdev.blueprints")

# ── Legacy Blueprints (v1 API, pre-existing) ──
workflow_bp = Blueprint('workflow', __name__)

pipeline_bp = Blueprint('pipeline', __name__)

@pipeline_bp.route("/api/pipeline/info", methods=["GET"])
def pipeline_info():
    """#1: Pipeline system info (extracted from app.py)."""
    return jsonify({
        "status": "success",
        "version": "2.0",
        "features": [
            "topological_sort",
            "parallel_execution",
            "rate_limiting",
            "retry_with_backoff",
            "partial_failure_detection",
            "scheduler_backoff"
        ]
    })


# ── Domain Route Blueprints (extracted from app.py) ──
_ROUTE_BLUEPRINTS = [
    # #25: Unified health check (must load first for /api/health availability)
    ("health_bp", "visualizer.blueprints.health_bp", "health_bp"),
    ("ceo_routes_bp", "visualizer.blueprints.ceo_routes_bp", "ceo_routes_bp"),
    ("workflow_engine_routes_bp", "visualizer.blueprints.workflow_engine_routes_bp", "workflow_engine_routes_bp"),
    ("governance_routes_bp", "visualizer.blueprints.governance_routes_bp", "governance_routes_bp"),
    ("brain_routes_bp", "visualizer.blueprints.brain_routes_bp", "brain_routes_bp"),
    ("workflow_routes_bp", "visualizer.blueprints.workflow_routes_bp", "workflow_routes_bp"),
    ("ai_routes_bp", "visualizer.blueprints.ai_routes_bp", "ai_routes_bp"),
    ("books_routes_bp", "visualizer.blueprints.books_routes_bp", "books_routes_bp"),
    ("gdrive_routes_bp", "visualizer.blueprints.gdrive_routes_bp", "gdrive_routes_bp"),
    # C-1: Split blueprints extracted from misc_routes_bp.py
    ("knowledge_routes_bp", "visualizer.blueprints.knowledge_routes_bp", "knowledge_bp"),
    ("team_routes_bp", "visualizer.blueprints.team_routes_bp", "team_bp"),
    ("config_routes_bp", "visualizer.blueprints.config_routes_bp", "config_bp"),
    ("stats_routes_bp", "visualizer.blueprints.stats_routes_bp", "stats_bp"),
    # D-3: OpenAPI docs + Swagger UI
    ("openapi_bp", "visualizer.blueprints.openapi_bp", "openapi_bp"),
    # Original monolith (still contains remaining routes)
    ("misc_routes_bp", "visualizer.blueprints.misc_routes_bp", "misc_routes_bp"),
    ("bookclub_routes_bp", "visualizer.blueprints.bookclub_routes_bp", "bookclub_routes_bp"),
    ("seminar_routes_bp", "visualizer.blueprints.seminar_routes_bp", "seminar_routes_bp"),
    ("finetune_bp", "visualizer.blueprints.finetune_routes_bp", "finetune_bp"),
    # Workflow Designer (easy mode)
    ("workflow_designer", "visualizer.blueprints.workflow_designer_routes_bp", "workflow_designer_bp"),
    # Quality & Productivity (Phase 1+2)
    ("quality", "visualizer.blueprints.quality_routes_bp", "quality_bp"),
]

_blueprints_registered = False

def register_blueprints(app):
    """Register all domain-specific route blueprints with the Flask app.
    
    Each blueprint is loaded in isolation — if one fails, the others
    still get registered, and a warning is logged.
    Idempotent: safe to call multiple times (second call is a no-op).
    """
    global _blueprints_registered
    if _blueprints_registered:
        logger.info("✅ Blueprints already registered (skipping duplicate call)")
        return
    _blueprints_registered = True
    # Legacy v1 blueprints
    try:
        from visualizer.blueprints.ceo_bp import ceo_bp
        app.register_blueprint(ceo_bp, url_prefix="/api/v1/ceo")
    except Exception as e:
        logger.warning(f"Legacy ceo_bp registration skipped: {e}")

    try:
        from visualizer.blueprints.ai_engine_bp import ai_engine_bp
        app.register_blueprint(ai_engine_bp, url_prefix="/api/v1/ai")
    except Exception as e:
        logger.warning(f"Legacy ai_engine_bp registration skipped: {e}")

    try:
        from visualizer.blueprints.brain_bp import brain_bp
        app.register_blueprint(brain_bp, url_prefix="/api/v1/brain")
    except Exception as e:
        logger.warning(f"Legacy brain_bp registration skipped: {e}")

    try:
        from visualizer.blueprints.fleet_bp import fleet_bp
        app.register_blueprint(fleet_bp, url_prefix="/api/v1/fleet")
    except Exception as e:
        logger.warning(f"Legacy fleet_bp registration skipped: {e}")

    try:
        from visualizer.blueprints.monitoring_bp import monitoring_bp
        app.register_blueprint(monitoring_bp, url_prefix="/api/v1/monitoring")
    except Exception as e:
        logger.warning(f"Legacy monitoring_bp registration skipped: {e}")

    # Domain route blueprints (extracted from app.py)
    registered = []
    failed = []
    already_registered_names = set(app.blueprints.keys()) if app.blueprints else set()
    
    # Reset _got_registered_once on all Blueprint objects that may be cached in sys.modules
    # This handles the case where the module-level code has already run (e.g., SocketIO reload)
    import sys as _sys
    for bp_name, module_path, attr_name in _ROUTE_BLUEPRINTS:
        if module_path in _sys.modules:
            mod = _sys.modules[module_path]
            bp = getattr(mod, attr_name, None)
            if bp and getattr(bp, '_got_registered_once', False):
                bp._got_registered_once = False
    
    for bp_name, module_path, attr_name in _ROUTE_BLUEPRINTS:
        try:
            import importlib
            # Skip if already registered in the current app
            if module_path in _sys.modules:
                mod = _sys.modules[module_path]
                bp = getattr(mod, attr_name, None)
                if bp and bp.name in already_registered_names:
                    registered.append(bp_name)
                    continue
            
            mod = importlib.import_module(module_path)
            bp = getattr(mod, attr_name)
            # Skip if already registered
            if bp.name in already_registered_names:
                registered.append(bp_name)
                continue
            app.register_blueprint(bp)
            already_registered_names.add(bp.name)
            registered.append(bp_name)
        except Exception as e:
            failed.append((bp_name, str(e)))
            logger.warning(f"⚠️ Blueprint '{bp_name}' registration failed: {e}")

    logger.info(
        f"✅ Blueprints registered: {len(registered)}/{len(_ROUTE_BLUEPRINTS)} "
        f"({', '.join(registered)})"
    )
    if failed:
        logger.warning(
            f"⚠️ Failed blueprints: {len(failed)} — "
            + ", ".join(f"{n}: {e[:50]}" for n, e in failed)
        )
