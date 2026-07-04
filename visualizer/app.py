# =========== Copyright 2026 @ ChatDev Overhaul Team. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2026 @ ChatDev Overhaul Team. All Rights Reserved. ===========

import logging
import os
import re
import signal
import argparse
import json
import glob
import time
import threading
import math
import random
import string
from datetime import datetime, timedelta
from collections import deque
from flask import Flask, send_from_directory, request, jsonify, send_file, redirect
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
import socketio
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── #4: Centralized Path Constants ──
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPANY_CONFIG_DIR = os.path.join(ROOT_DIR, "CompanyConfig")
TEAMS_DIR = os.path.join(COMPANY_CONFIG_DIR, "Teams")
BLUEPRINTS_DIR = os.path.join(COMPANY_CONFIG_DIR, "Blueprints")
VISUALIZER_DIR = os.path.dirname(os.path.abspath(__file__))

# ── #26: Structured JSON Log Formatter ──
class StructuredJsonFormatter(logging.Formatter):
    """#26: Output structured JSON logs for consistent machine-parseable logging."""
    def format(self, record):
        log_entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)

_structured_fmt = StructuredJsonFormatter()
# Apply to chatdev loggers (opt-in to avoid disrupting dev console output)
for _logger_name in ("chatdev", "chatdev.database", "chatdev.state_engine", "access"):
    _lg = logging.getLogger(_logger_name)
    if not _lg.handlers:
        _handler = logging.StreamHandler()
        _handler.setFormatter(_structured_fmt)
        _lg.addHandler(_handler)
        _lg.setLevel(logging.INFO)

from chatdev.conversational_alignment import generate_alignment_questions, synthesize_custom_pipeline

# ── #2/#6/#7/#12/#18/#19/#20/#24: Shared Workflow Utilities ──
from visualizer.workflow_utils import (
    topological_sort as unified_topological_sort,
    validate_filename, safe_resolve_path,
    validate_file_size, MAX_KNOWLEDGE_FILE_SIZE,
    get_team_lock,
    cleanup_execution_history,
    workflow_rate_limiter, llm_rate_limiter,
    retry_with_backoff,
    save_daily_metering_rollup, load_metering_history,
)

# ── #5: Lazy Import Registry (cache modules to avoid per-request import cost) ──
_lazy_import_cache = {}
_lazy_import_lock = threading.Lock()

def lazy_import(module_path, attr_name=None):
    """#5: Import a module/attribute once and cache it.
    Usage: FleetManager = lazy_import('chatdev.fleet_manager', 'FleetManager')
    """
    cache_key = f"{module_path}.{attr_name}" if attr_name else module_path
    
    cached = _lazy_import_cache.get(cache_key)
    if cached is not None:
        return cached
    
    with _lazy_import_lock:
        # Double-check after acquiring lock
        cached = _lazy_import_cache.get(cache_key)
        if cached is not None:
            return cached
        
        import importlib
        module = importlib.import_module(module_path)
        result = getattr(module, attr_name) if attr_name else module
        _lazy_import_cache[cache_key] = result
        return result

# ── #15: Path Traversal Defense ──
def validate_team_name(name):
    """Validate team name to prevent path traversal attacks. Returns (is_valid, sanitized_name)."""
    if not name or not isinstance(name, str):
        return False, ""
    # Only allow alphanumeric, underscore, hyphen
    if not re.match(r'^[A-Za-z0-9_-]+$', name):
        return False, ""
    # Prevent path traversal
    if '..' in name or '/' in name or '\\' in name:
        return False, ""
    return True, name

def sanitize_path_component(component):
    """Sanitize any path component to prevent directory traversal."""
    if not component or not isinstance(component, str):
        return ""
    return re.sub(r'[^A-Za-z0-9_\-. ]', '', component).strip()

# ── #16: Safe Error Response Helper ──
_PRODUCTION_MODE = os.environ.get('FLASK_ENV', 'development') == 'production'

def safe_error_response(error, context="", status_code=500):
    """#16: Return sanitized error to client, log full details server-side.
    In production: generic message. In dev: limited error info (no stack traces).
    """
    logging.error(f"[{context or 'API'}] {type(error).__name__}: {error}")
    if _PRODUCTION_MODE:
        msg = "서버 내부 오류가 발생했습니다"  # Generic Korean error
    else:
        # Dev mode: show error type but not full traceback or file paths
        msg = f"{type(error).__name__}: {str(error)[:200]}"
    return jsonify({"status": "error", "message": msg}), status_code

# ── #29: Standardized Response Envelope Helpers ──
def api_success(data=None, message="", **extra):
    """#29: Standard success response envelope.
    Returns: jsonify({"status": "success", "data": ..., "message": ...})
    """
    resp = {"status": "success"}
    if message:
        resp["message"] = message
    if data is not None:
        resp["data"] = data
    resp.update(extra)
    return jsonify(resp)

def api_error(message="오류가 발생했습니다", status_code=400, **extra):
    """#29: Standard error response envelope.
    Returns: (jsonify({"status": "error", "message": ...}), status_code)
    """
    resp = {"status": "error", "message": message}
    resp.update(extra)
    return jsonify(resp), status_code

# ── .env Auto-Loader (zero dependencies) ──
def _load_dotenv():
    """Load .env file from project root into os.environ (no pip install needed)."""
    project_root = ROOT_DIR  # #4
    env_path = os.path.join(project_root, ".env")
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and not value.startswith('your_'):
                    os.environ.setdefault(key, value)
        return True
    return False

_env_loaded = _load_dotenv()
_has_google_creds = (
    bool(os.environ.get("GOOGLE_CLIENT_ID"))
    and bool(os.environ.get("GOOGLE_CLIENT_SECRET"))
    and "your_" not in os.environ.get("GOOGLE_CLIENT_ID", "")
    and "your_" not in os.environ.get("GOOGLE_CLIENT_SECRET", "")
    and len(os.environ.get("GOOGLE_CLIENT_ID", "")) > 20
)

app = Flask(__name__, static_folder='static')

# ── #1,#2,#5,#8,#15,#16,#21: Load backend utilities ──
try:
    from visualizer.backend_utils import (
        config as app_config, init_all_security, api_ok, api_err,
        validate_json, sanitize_string, validate_image_upload,
        commands_lock, pipeline_lock, brain_lock, upload_lock,
        get_db_connection, deep_health_check, safe_external_request,
        safe_system_stats, save_pipeline_state, load_pipeline_states,
        find_duplicate_knowledge, cleanup_expired_uploads, backup_database,
        extract_technologies, run_migrations
    )
    app.config['SECRET_KEY'] = app_config.ensure_secret_key()
    _backend_utils_ok = True
except Exception as _bu_err:
    logging.warning(f"[BackendUtils] Not loaded: {_bu_err}")
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(32).hex())  # #14: Never hardcode secret
    _backend_utils_ok = False

# Enable Flask-SocketIO server with rooms
# #13: Restrict CORS in production, allow localhost in dev
_cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000').split(',')
socketio_server = SocketIO(app, cors_allowed_origins=_cors_origins)
# #17: 500MB global limit for large PDF uploads
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB global limit

# Initialize security & utilities (#1,#2,#5,#8,#15,#16,#23,#26)
if _backend_utils_ok:
    try:
        init_all_security(app)
    except Exception as _init_err:
        logging.warning(f"[BackendUtils] Init partial: {_init_err}")

# Suppress noisy console logs from Werkzeug
app.logger.setLevel(logging.ERROR)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ── #1: Register Blueprints for modular architecture ──
try:
    from visualizer.blueprints import pipeline_bp
    app.register_blueprint(pipeline_bp)
    logging.info("#1: Blueprints registered: pipeline")
except Exception as _bp_err:
    logging.warning(f"#1: Blueprint registration skipped: {_bp_err}")

# ── #26: Correlation ID Middleware for request tracing ──
import uuid as _uuid
from flask import g

@app.before_request
def _inject_correlation_id():
    """#26: Attach unique correlation ID to every request for log tracing."""
    g.correlation_id = request.headers.get('X-Correlation-ID', _uuid.uuid4().hex[:12])

@app.after_request
def _attach_correlation_id(response):
    """#26: Echo correlation ID in response headers."""
    cid = getattr(g, 'correlation_id', None)
    if cid:
        response.headers['X-Correlation-ID'] = cid
    return response

# ── #29: Global Error Handlers for consistent API response format ──
@app.errorhandler(404)
def _handle_404(e):
    return jsonify({"status": "error", "message": "리소스를 찾을 수 없습니다", "code": 404}), 404

@app.errorhandler(413)
def _handle_413(e):
    return jsonify({"status": "error", "message": "요청 크기가 너무 큽니다 (최대 500MB)", "code": 413}), 413

@app.errorhandler(500)
def _handle_500(e):
    cid = getattr(g, 'correlation_id', 'unknown')
    logging.error(f"[500] correlation_id={cid} error={e}")
    return jsonify({"status": "error", "message": "서버 내부 오류", "code": 500, "correlation_id": cid}), 500

# ── #11: Static File Cache Headers ──
@app.after_request
def _add_cache_headers(response):
    """#11: Add appropriate cache headers for static assets."""
    if request.path.startswith('/static/'):
        if request.path.endswith(('.css', '.js', '.woff2', '.woff', '.ttf')):
            # Long cache for versioned assets
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        elif request.path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico')):
            response.headers['Cache-Control'] = 'public, max-age=86400'  # 1 day for images
        elif request.path.endswith('.html'):
            response.headers['Cache-Control'] = 'no-cache, must-revalidate'
    return response

# ── #10: Request Timeout Guard ──
REQUEST_TIMEOUT_SECONDS = int(os.environ.get('REQUEST_TIMEOUT_SECONDS', '120'))

@app.before_request
def _set_request_start_time():
    """#10: Record request start time for timeout monitoring."""
    request._start_time = time.time()

@app.after_request
def _check_request_timeout(response):
    """#10: Log slow requests that exceed the timeout threshold."""
    start = getattr(request, '_start_time', None)
    if start:
        elapsed = time.time() - start
        if elapsed > REQUEST_TIMEOUT_SECONDS:
            logging.warning(
                f"⏰ Slow request: {request.method} {request.path} "
                f"took {elapsed:.1f}s (limit: {REQUEST_TIMEOUT_SECONDS}s)"
            )
        # Inject Server-Timing header for observability
        response.headers['Server-Timing'] = f'total;dur={elapsed * 1000:.0f}'
    return response

# ── #18: Structured JSON Request Logging ──
_access_logger = logging.getLogger("access")

@app.after_request
def _structured_request_log(response):
    """#18: Emit structured JSON log for every API request (for log aggregation)."""
    if request.path.startswith('/static/') or request.path == '/favicon.ico':
        return response  # Skip static assets
    start = getattr(request, '_start_time', None)
    duration_ms = round((time.time() - start) * 1000, 1) if start else 0
    cid = getattr(g, 'correlation_id', '-')
    log_entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "method": request.method,
        "path": request.path,
        "status": response.status_code,
        "duration_ms": duration_ms,
        "cid": cid,
        "ip": request.remote_addr,
        "size": response.content_length or 0,
    }
    _access_logger.info(json.dumps(log_entry, ensure_ascii=False))
    return response

# ══════════════════════════════════════════════════════════════
#  Enterprise Infrastructure Integration (30-Item Backend Upgrade)
#  #2: ServiceContainer replaces flat _ENTERPRISE_MODULES dict
#  #14: DeferredModuleLoader handles V3/V4/V5 background loading
# ══════════════════════════════════════════════════════════════
from visualizer.core.container import ServiceContainer
from visualizer.module_loader import _safe_load_module, bootstrap_enterprise_modules

container = ServiceContainer()
app.config['CONTAINER'] = container

# Backward compatibility alias
_ENTERPRISE_MODULES = container.load_status

try:
    # Phase 1: Core Infrastructure
    from visualizer.core.config import get_config
    _cfg = get_config()
    _ENTERPRISE_MODULES['config'] = True

    from visualizer.core.event_bus import event_bus, Events
    _ENTERPRISE_MODULES['event_bus'] = True

    from visualizer.core.task_queue import task_queue
    task_queue.start_worker()
    _ENTERPRISE_MODULES['task_queue'] = True

    from visualizer.core.metrics import register_metrics
    register_metrics(app)
    _ENTERPRISE_MODULES['metrics'] = True

    # Phase 2: Security
    from visualizer.core.security import register_security
    register_security(app, cors_origins=getattr(_cfg, 'CORS_ORIGINS', ['*']))
    _ENTERPRISE_MODULES['security'] = True

    from visualizer.core.middleware import register_middleware
    register_middleware(app, default_rate_limit=getattr(_cfg, 'RATE_LIMIT_DEFAULT', '100/minute'))
    _ENTERPRISE_MODULES['middleware'] = True

    # #35: Static file gzip compression
    @app.after_request
    def _gzip_response(response):
        """Compress text responses > 500 bytes."""
        if (response.status_code == 200 and
            response.content_length and response.content_length > 500 and
            'gzip' in request.headers.get('Accept-Encoding', '') and
            response.content_type and
            any(t in response.content_type for t in ('text/', 'application/json', 'application/javascript'))):
            try:
                import gzip
                data = response.get_data()
                compressed = gzip.compress(data, compresslevel=6)
                if len(compressed) < len(data):
                    response.set_data(compressed)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Length'] = len(compressed)
                    response.headers['Vary'] = 'Accept-Encoding'
            except Exception as e:
                logging.debug(f"[gzip] compression skipped: {e}")
        return response

    # #33: Thread manager initialization
    try:
        from visualizer.core.thread_manager import register_thread  # noqa: F401
        _ENTERPRISE_MODULES['thread_manager'] = True
    except ImportError as e:
        logging.debug(f"[thread_manager] optional module unavailable: {e}")

    # Phase 1 continued: Blueprints
    from visualizer.blueprints import register_blueprints
    register_blueprints(app)
    _ENTERPRISE_MODULES['blueprints'] = True

    # Phase 3: Services
    from visualizer.services.auto_learner import auto_learner
    _ENTERPRISE_MODULES['auto_learner'] = True

    from visualizer.services.rag_service import rag_service
    _ENTERPRISE_MODULES['rag_service'] = True

    from visualizer.services.benchmark_service import benchmark_service
    _ENTERPRISE_MODULES['benchmark_service'] = True

    from visualizer.services.context_injector import context_injector
    _ENTERPRISE_MODULES['context_injector'] = True

    from visualizer.services.result_analyzer import result_analyzer
    _ENTERPRISE_MODULES['result_analyzer'] = True

    from visualizer.services.multi_model import multi_model
    _ENTERPRISE_MODULES['multi_model'] = True

    from visualizer.services.agent_memory import agent_memory
    _ENTERPRISE_MODULES['agent_memory'] = True

    from visualizer.services.api_key_manager import api_key_manager
    _ENTERPRISE_MODULES['api_key_manager'] = True

    from visualizer.services.backup_service import backup_service
    _ENTERPRISE_MODULES['backup_service'] = True

    # #29: Temp file cleanup service
    def _load_cleanup():
        from visualizer.services.cleanup import init_cleanup
        data_dir = os.path.join(ROOT_DIR, "data")
        init_cleanup(data_dir)
    _safe_load_module('cleanup', _load_cleanup)

    # #30: Log rotation — write to data/logs/ with 10MB rotation
    try:
        from visualizer.core.structured_logger import configure_structured_logging
        log_dir = os.path.join(ROOT_DIR, "data", "logs")
        os.makedirs(log_dir, exist_ok=True)
        configure_structured_logging(
            "chatdev",
            log_file=os.path.join(log_dir, "chatdev.log"),
            max_bytes=10 * 1024 * 1024,
            backup_count=5,
        )
    except Exception as e:
        logging.warning(f"[Init] Log rotation setup failed: {e}")

    # ── V2 Enterprise Modules (30-Item Phase 2) ──
    # #2: Each module loaded in isolation via _safe_load_module

    def _load_db_pool():
        from visualizer.core.db_pool import get_pool  # noqa: F401
    _safe_load_module('db_pool', _load_db_pool)

    def _load_interface_layer():
        from visualizer.core.interface_layer import register_visualizer_services
        register_visualizer_services()
    _safe_load_module('interface_layer', _load_interface_layer)

    def _load_socketio_ns():
        from visualizer.core.socketio_namespaces import register_namespaces
        register_namespaces(socketio_server)
    _safe_load_module('socketio_ns', _load_socketio_ns)

    def _load_error_handler():
        from visualizer.core.error_handler import register_error_handlers
        register_error_handlers(app)
    _safe_load_module('error_handler', _load_error_handler)

    def _load_config_store():
        from visualizer.core.config_store import config_store
        config_store.start_watching()
    _safe_load_module('config_store', _load_config_store)

    def _load_response_envelope():
        from visualizer.core.response_envelope import success, error, paginated  # noqa: F401
    _safe_load_module('response_envelope', _load_response_envelope)

    def _load_smart_router():
        from visualizer.services.smart_router import smart_router  # noqa: F401
    _safe_load_module('smart_router', _load_smart_router)

    def _load_prompt_engine():
        from visualizer.services.prompt_engine import prompt_engine  # noqa: F401
    _safe_load_module('prompt_engine', _load_prompt_engine)

    def _load_streaming():
        from visualizer.services.streaming import register_streaming_routes
        register_streaming_routes(app)
    _safe_load_module('streaming', _load_streaming)

    def _load_model_scaler():
        from visualizer.services.model_scaler import model_scaler
        model_scaler.start_monitor()
    _safe_load_module('model_scaler', _load_model_scaler)

    def _load_context_window():
        from visualizer.services.context_window import conversation_manager  # noqa: F401
    _safe_load_module('context_window', _load_context_window)

    def _load_finetune():
        from visualizer.services.finetune_pipeline import finetune_pipeline  # noqa: F401
    _safe_load_module('finetune', _load_finetune)

    def _load_guardrails():
        from visualizer.services.guardrails import guardrails  # noqa: F401
    _safe_load_module('guardrails', _load_guardrails)

    def _load_multimodal():
        from visualizer.services.multimodal import multimodal  # noqa: F401
    _safe_load_module('multimodal', _load_multimodal)

    def _load_vector_search():
        from visualizer.services.vector_search import vector_search  # noqa: F401
    _safe_load_module('vector_search', _load_vector_search)

    def _load_knowledge_linker():
        from visualizer.services.knowledge_linker import knowledge_linker  # noqa: F401
    _safe_load_module('knowledge_linker', _load_knowledge_linker)

    def _load_execution_analyzer():
        from visualizer.services.execution_analyzer import execution_analyzer  # noqa: F401
    _safe_load_module('execution_analyzer', _load_execution_analyzer)

    def _load_command_chain():
        from visualizer.services.command_chain import command_chain  # noqa: F401
    _safe_load_module('command_chain', _load_command_chain)

    def _load_db_migrator():
        from visualizer.services.db_migrator import db_migrator
        db_migrator.migrate()
    _safe_load_module('db_migrator', _load_db_migrator)

    def _load_realtime_sync():
        from visualizer.services.realtime_sync import realtime_sync
        realtime_sync.start(socketio_server)
    _safe_load_module('realtime_sync', _load_realtime_sync)

    def _load_report_engine():
        from visualizer.services.report_engine import report_engine  # noqa: F401
    _safe_load_module('report_engine', _load_report_engine)

    def _load_obsidian_sync():
        from visualizer.services.obsidian_sync import obsidian_sync  # noqa: F401
    _safe_load_module('obsidian_sync', _load_obsidian_sync)

    def _load_self_healer():
        from visualizer.services.self_healer import self_healer
        self_healer.start_monitor()
    _safe_load_module('self_healer', _load_self_healer)

    def _load_log_engine():
        from visualizer.services.log_engine import log_store  # noqa: F401
    _safe_load_module('log_engine', _load_log_engine)

    def _load_dead_letter():
        from visualizer.services.dead_letter_recovery import dead_letter_recovery
        dead_letter_recovery.start_auto_recovery()
    _safe_load_module('dead_letter_recovery', _load_dead_letter)

    def _load_plugin_runtime():
        from visualizer.services.plugin_runtime import plugin_runtime  # noqa: F401
    _safe_load_module('plugin_runtime', _load_plugin_runtime)

    def _load_fleet_realtime():
        from visualizer.services.fleet_realtime import fleet_realtime
        fleet_realtime.start_monitoring()
    _safe_load_module('fleet_realtime', _load_fleet_realtime)

    def _load_ci_pipeline():
        from visualizer.services.ci_pipeline import ci_pipeline  # noqa: F401
    _safe_load_module('ci_pipeline', _load_ci_pipeline)

    # ── V3 Enterprise Modules (30-Item Phase 3) ──

    # ═══════════════════════════════════════════════════════════
    # #1/#14: V3/V4/V5/HuggingFace modules loaded in background
    # via DeferredModuleLoader (see module_loader.py)
    # Replaces ~130 lines of inline __import__ calls
    # ═══════════════════════════════════════════════════════════
    _deferred_loader = bootstrap_enterprise_modules(app, container, socketio_server)

    # Wire event handlers
    def _on_command_completed(event):
        """Auto-learn from completed commands + Hermes learning loop."""
        try:
            auto_learner.learn_from_command(
                event.data.get('command', ''), event.data.get('result', ''), 'completed'
            )
            # Hermes-style: Closed learning loop for playbook executions
            if event.data.get('playbook_id'):
                auto_learner.learn_from_execution(
                    exec_id=event.data.get('exec_id', ''),
                    playbook_id=event.data.get('playbook_id', ''),
                    result=event.data.get('result', ''),
                    metrics=event.data.get('metrics', {}),
                )
        except Exception as _e:
            logging.debug(f"[suppressed] Exception: {_e}")

        # Hermes-style: User observation
        try:
            from visualizer.services.user_model import user_model
            user_model.observe('execution_complete', {
                'playbook_id': event.data.get('playbook_id', ''),
                'command': event.data.get('command', '')[:100],
                'success': True,
            })
        except Exception as e:
            logging.debug(f"[user_model] observe(execution_complete) failed: {e}")

    def _on_command_failed(event):
        """Auto-learn from failed commands."""
        try:
            auto_learner.learn_from_command(
                event.data.get('command', ''), event.data.get('error', ''), 'failed'
            )
            # Hermes-style: Record failure for avoidance learning
            if event.data.get('playbook_id'):
                auto_learner.learn_from_execution(
                    exec_id=event.data.get('exec_id', ''),
                    playbook_id=event.data.get('playbook_id', ''),
                    result=event.data.get('error', ''),
                    metrics={'quality_score': 0.0},
                )
        except Exception as _e:
            logging.debug(f"[suppressed] Exception: {_e}")

    event_bus.on(Events.COMMAND_COMPLETED, _on_command_completed)
    event_bus.on(Events.COMMAND_FAILED, _on_command_failed)

    _stats = container.get_stats()
    _loaded = _stats["loaded"]
    _failed = _stats["failed"]

    event_bus.emit(Events.SYSTEM_STARTUP, {
        "modules_loaded": _loaded,
        "modules_failed": _failed,
        "modules": _stats["loaded_modules"],
        "failed_modules": _stats["failed_modules"],
    })

    logging.getLogger("chatdev").info(
        f"🏗️ Enterprise Infrastructure: {_loaded} modules loaded (Phase 1+2)"
        + (f" ({_failed} failed)" if _failed else "")
        + f" + {_deferred_loader._total_modules} deferred"
    )
except Exception as _enterprise_err:
    logging.warning(f"⚠️ Enterprise modules partial load ({len(_ENTERPRISE_MODULES)} loaded): {_enterprise_err}")

# In-memory team message store: { "Squad_A": deque([ ... ]) }
# #24: Use deque with maxlen to prevent unbounded memory growth
MAX_MESSAGES_PER_TEAM = 1000
messages = {}
# #30: Simple integer instead of mutable list
server_port = 8000
# #19: Thread-safety lock for squad_stats
_squad_stats_lock = threading.Lock()

# #6: Direct server emit replaces external socketio.Client
# Old pattern used _send_msg_client and _send_msg_connected (global mutable) causing race conditions
# and incompatibility with multi-worker deployments.

def send_msg(role, text):
    """#6: Broadcast log message via direct server-side emit.
    Replaces the old socketio.Client approach which created a separate TCP
    connection back to itself — wasteful and prone to race conditions.
    """
    try:
        team_name = os.environ.get('CHATDEV_TEAM_NAME', 'Squad_A')
        socketio_server.emit('client_message', {
            "role": role, "text": text, "team_name": team_name
        }, namespace='/')
    except Exception as e:
        logging.debug(f"[send_msg] Emit failed: {e}")

# ==========================================
#          Persistent State Engine (DB-backed)
# ==========================================

try:
    from visualizer.backend.state_engine import (
        persistent_squad_stats, persistent_approval_states,
        persistent_executive_states, persistent_connector_configs,
        persistent_chat_history, telemetry_engine,
    )
    squad_stats = persistent_squad_stats
    _PERSISTENT_STATE = True
except Exception as _pse:
    squad_stats = {}
    _PERSISTENT_STATE = False
    logging.warning(f"State engine not available, using in-memory: {_pse}")

def get_stats_file_path():
    return os.path.join(VISUALIZER_DIR, "squad_stats.json")  # #4: Use constant

# ── #9: JSON File Cache with mtime-based invalidation ──
_json_file_cache = {}
_json_cache_lock = threading.Lock()

def cached_json_read(filepath, default=None):
    """#9: Read JSON file with mtime-based cache. Avoids re-reading unchanged files.
    Returns cached data if file hasn't changed since last read.
    """
    try:
        mtime = os.path.getmtime(filepath)
    except OSError:
        return default if default is not None else {}
    
    with _json_cache_lock:
        cached = _json_file_cache.get(filepath)
        if cached and cached['mtime'] == mtime:
            return cached['data']
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        with _json_cache_lock:
            _json_file_cache[filepath] = {'data': data, 'mtime': mtime}
        return data
    except Exception:
        return default if default is not None else {}

def invalidate_json_cache(filepath):
    """#9: Explicitly invalidate a cached JSON entry after writes."""
    with _json_cache_lock:
        _json_file_cache.pop(filepath, None)

def _generate_default_throughput():
    """#8: Generate dynamic throughput dates instead of hardcoded values."""
    return [{"date": (datetime.now() - timedelta(days=i)).strftime("%m-%d"), "count": 0} for i in range(6, -1, -1)]

def load_squad_stats():
    global squad_stats
    path = get_stats_file_path()
    with _squad_stats_lock:  # #19: Thread safety for reads too
        if os.path.exists(path):
            try:
                data = cached_json_read(path, default={})  # #9: Use file cache
                squad_stats.update(data)
            except Exception as _e:
                logging.debug(f"[suppressed] Exception: {_e}")
    # Self-heal: auto-discover teams from CompanyConfig/Teams/ and seed any missing stats
    discovered_teams = []
    if os.path.isdir(TEAMS_DIR):  # #4: Use constant
        discovered_teams = [d for d in os.listdir(TEAMS_DIR)
                            if os.path.isdir(os.path.join(TEAMS_DIR, d)) and not d.startswith('_')]
    # Also keep legacy names as fallback
    for s in set(discovered_teams + ["Squad_A"]):
        if s not in squad_stats:
            squad_stats[s] = {
                "active_tasks": 0,
                "token_cost": 0.0,
                "completed_tasks": 0,
                "throughput": _generate_default_throughput(),  # #8: Dynamic dates
                "workload": {},
                "cost_efficiency": 0.0
            }
    save_squad_stats()

def save_squad_stats():
    """#21: Atomic write pattern to prevent file corruption on concurrent access."""
    path = get_stats_file_path()
    with _squad_stats_lock:  # #19: Thread safety
        tmp_path = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(tmp_path, 'w', encoding='utf-8') as f:
                dump_data = dict(squad_stats.items()) if hasattr(squad_stats, 'items') else squad_stats
                json.dump(dump_data, f, indent=4, ensure_ascii=False)
            os.replace(tmp_path, path)  # Atomic on POSIX
        except Exception as e:
            logging.error(f"Error saving squad stats: {e}")
            # Cleanup temp file on failure
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass  # Ignored

load_squad_stats()

# ==========================================
#   🏗️ Backend Infrastructure Bootstrap
#   10대 엔터프라이즈 백엔드 모듈 초기화
# ==========================================

def _bootstrap_backend_infrastructure():
    """
    Initialize all enterprise backend infrastructure modules.
    Each module is loaded independently — failures are isolated.
    """
    modules_loaded = []
    modules_failed = []

    # ── 1. Structured Logging (must be first) ──
    try:
        from visualizer.backend.logging_engine import (
            setup_logging, register_request_logging, register_audit_routes
        )
        log_file = os.path.join(
            VISUALIZER_DIR, "data", "chatdev.log"
        )
        setup_logging(app, log_file=log_file)
        register_request_logging(app)
        register_audit_routes(app)
        modules_loaded.append("logging_engine")
    except Exception as e:
        modules_failed.append(("logging_engine", str(e)))

    # ── 2. Database Layer ──
    try:
        from visualizer.backend.database import init_database, register_db_routes
        init_database()
        register_db_routes(app)
        modules_loaded.append("database")
    except Exception as e:
        modules_failed.append(("database", str(e)))

    # ── 3. Authentication & Authorization ──
    try:
        from visualizer.backend.auth import register_auth_routes
        register_auth_routes(app)
        modules_loaded.append("auth")
    except Exception as e:
        modules_failed.append(("auth", str(e)))

    # ── 4. Rate Limiter ──
    try:
        from visualizer.backend.rate_limiter import register_rate_limiter
        register_rate_limiter(app, global_limit=120, per_seconds=60)
        modules_loaded.append("rate_limiter")
    except Exception as e:
        modules_failed.append(("rate_limiter", str(e)))

    # ── 5. Health Checks ──
    try:
        from visualizer.backend.health import register_health_routes
        register_health_routes(app)
        modules_loaded.append("health")
    except Exception as e:
        modules_failed.append(("health", str(e)))

    # ── 6. Error Handlers & Retry Engine ──
    try:
        from visualizer.backend.retry_engine import register_error_handlers
        register_error_handlers(app)
        modules_loaded.append("retry_engine")
    except Exception as e:
        modules_failed.append(("retry_engine", str(e)))

    # ── 7. Response Cache ──
    try:
        from visualizer.backend.cache import register_cache_routes
        register_cache_routes(app)
        modules_loaded.append("cache")
    except Exception as e:
        modules_failed.append(("cache", str(e)))

    # ── 8. Webhook Queue ──
    try:
        from visualizer.backend.webhook_queue import register_webhook_routes
        register_webhook_routes(app)
        modules_loaded.append("webhook_queue")
    except Exception as e:
        modules_failed.append(("webhook_queue", str(e)))

    # ── 9. API Docs & Versioning ──
    try:
        from visualizer.backend.api_docs import register_api_docs
        register_api_docs(app)
        modules_loaded.append("api_docs")
    except Exception as e:
        modules_failed.append(("api_docs", str(e)))

    # ── 10. Persistent State Engine ──
    try:
        from visualizer.backend.state_engine import init_state_schema
        init_state_schema()
        modules_loaded.append("state_engine")
    except Exception as e:
        modules_failed.append(("state_engine", str(e)))

    # ── 11. Cost Calculator ──
    try:
        from visualizer.backend.cost_calculator import list_all_models
        _models = list_all_models()
        modules_loaded.append(f"cost_calculator ({len(_models)} models)")
    except Exception as e:
        modules_failed.append(("cost_calculator", str(e)))

    # ── 12. Workflow Recovery Engine ──
    try:
        from visualizer.backend.workflow_recovery import recovery_engine
        modules_loaded.append("workflow_recovery")
    except Exception as e:
        modules_failed.append(("workflow_recovery", str(e)))

    # ── 13. Persistent Scheduler ──
    try:
        from visualizer.backend.persistent_scheduler import scheduler
        scheduler.start()
        modules_loaded.append("persistent_scheduler")
    except Exception as e:
        modules_failed.append(("persistent_scheduler", str(e)))

    # ── 14. Integration Hub ──
    try:
        from visualizer.backend.integration_hub import (
            slack_client, discord_client, gdrive_client,
            connector_manager
        )
        modules_loaded.append("integration_hub")
    except Exception as e:
        modules_failed.append(("integration_hub", str(e)))

    # ── Summary ──
    total_modules = len(modules_loaded) + len(modules_failed)
    logging.info(f"\n{'='*60}")
    logging.info(f"  🏗️ Backend Infrastructure Bootstrap Complete")
    logging.info(f"  ✅ Loaded: {len(modules_loaded)}/{total_modules} modules")
    if modules_loaded:
        for m in modules_loaded:
            logging.info(f"     ✅ {m}")
    if modules_failed:
        logging.info(f"  ⚠️  Failed: {len(modules_failed)} modules")
        for m, err in modules_failed:
            logging.info(f"     ❌ {m}: {err[:80]}")
    logging.info(f"{'='*60}\n")

_bootstrap_backend_infrastructure()

def initialize_default_teams():
    root_dir = ROOT_DIR  # #4: Use constant
    preloads = [
        ("Development_Team", "software"),
        ("Marketing_Team", "youtube")
    ]
    for team_name, industry_id in preloads:
        team_dir = os.path.join(root_dir, "CompanyConfig", "Teams", team_name)
        if not os.path.exists(os.path.join(team_dir, "SquadConfig.json")):
            try:
                blueprint_path = os.path.join(root_dir, "CompanyConfig", "Blueprints", f"{industry_id}.json")
                if os.path.exists(blueprint_path):
                    with open(blueprint_path, 'r', encoding='utf-8') as f:
                        blueprint = json.load(f)
                    
                    os.makedirs(team_dir, exist_ok=True)
                    
                    squad_config_data = blueprint.get("squad_config", {})
                    squad_config_data["_ontology"] = blueprint.get("ontology", {})
                    squad_config_data["_industry_id"] = industry_id
                    squad_config_data["_industry_name"] = blueprint.get("industry_name")
                    
                    with open(os.path.join(team_dir, "SquadConfig.json"), 'w', encoding='utf-8') as sf:
                        json.dump(squad_config_data, sf, indent=4, ensure_ascii=False)
                        
                    chatchain_config_data = {
                        "recruitments": blueprint.get("recruitments", []),
                        "nodes": blueprint.get("default_nodes", []),
                        "edges": blueprint.get("default_edges", [])
                    }
                    with open(os.path.join(team_dir, "ChatChainConfig.json"), 'w', encoding='utf-8') as cf:
                        json.dump(chatchain_config_data, cf, indent=4, ensure_ascii=False)
                    
                    preloaded_knowledge = blueprint.get("preloaded_knowledge", {})
                    knowledge_dir = os.path.join(root_dir, "CompanyConfig", "Knowledge")
                    os.makedirs(knowledge_dir, exist_ok=True)
                    for filename, content in preloaded_knowledge.items():
                        with open(os.path.join(knowledge_dir, filename), 'w', encoding='utf-8') as kf:
                            kf.write(content)
                            
                    global squad_injected_knowledge
                    squad_injected_knowledge[team_name] = list(preloaded_knowledge.keys())
            except Exception as e:
                logging.debug(f"[suppressed] Exception as e: {e}")

# C-3: Lazy initialization — defer to first request instead of module load
_teams_initialized = False

def _lazy_init_teams():
    """Initialize teams on first request instead of at import time."""
    global _teams_initialized
    if _teams_initialized:
        return
    _teams_initialized = True
    try:
        initialize_default_teams()
    except Exception as e:
        logging.warning(f"[LazyInit] initialize_default_teams failed: {e}")

@app.before_request
def _ensure_teams_initialized():
    _lazy_init_teams()

# ==========================================
#          Subdirectory Routing & Views
# ==========================================

try:
    from chatdev.mcp_client import mcp_hub
except ImportError:
    mcp_hub = None

try:
    from chatdev.secure_vault import vault as secure_vault
except ImportError:
    secure_vault = None

SAVED_WORKFLOWS_DIR = os.path.join(VISUALIZER_DIR, "saved_workflows")  # #4: Use constant
os.makedirs(SAVED_WORKFLOWS_DIR, exist_ok=True)

if _PERSISTENT_STATE:
    approval_states = persistent_approval_states
    connector_configs = persistent_connector_configs
    _chat_history = persistent_chat_history
else:
    approval_states = {}
    connector_configs = {}
    _chat_history = {}
squad_injected_knowledge = {}

# ── In-Memory Knowledge RAG Store ──
# C-2 TODO: These inline RAG functions duplicate knowledge_rag.py — delegate to that module.
# Full extraction deferred to separate refactor PR to avoid breaking changes.
_knowledge_chunks = {}  # { team_name: [ { "source": filename, "chunk": text, "keywords": set } ] }
_indexing_status = {}   # { job_id: { files: [...], current_file, phase, progress, ... } }

def _clean_ocr_text(text):
    """#3: Clean OCR text — remove broken Unicode, normalize spacing."""
    import re
    import unicodedata
    # Remove control characters (except newlines/tabs)
    text = ''.join(c for c in text if unicodedata.category(c)[0] != 'C' or c in '\n\t\r')
    # Remove isolated CJK ideographs mixed with garbled text (common OCR noise)
    text = re.sub(r'[^\u0000-\u007F\uAC00-\uD7A3\u3131-\u3163\u1100-\u11FF\s.,!?;:\'\"()\-\u2013\u2014\u2018\u2019\u201C\u201D\u300C\u300D\u3001\u3002\uFF01\uFF1F0-9a-zA-Z\u00C0-\u024F]{2,}', '', text)
    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Filter lines with low Korean/ASCII ratio (noise)
    clean_lines = []
    for line in text.split('\n'):
        if not line.strip():
            clean_lines.append('')
            continue
        # Count meaningful chars (Korean + ASCII letters + digits)
        meaningful = sum(1 for c in line if ('\uAC00' <= c <= '\uD7A3') or c.isascii())
        ratio = meaningful / max(len(line), 1)
        if ratio >= 0.3 or len(line) < 5:  # Keep if 30%+ meaningful or very short
            clean_lines.append(line)
    return '\n'.join(clean_lines).strip()


def _extract_text_from_file(filepath, filename):
    """Extract text from various file formats including PDF."""
    ext = os.path.splitext(filename)[1].lower()

    # PDF extraction
    if ext == '.pdf':
        try:
            import PyPDF2
            text_parts = []
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                total_pages = len(reader.pages)
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            full_text = "\n\n".join(text_parts)
            # #3: OCR post-processing
            full_text = _clean_ocr_text(full_text)
            logging.info(f"[PDF] Extracted {len(full_text)} chars from {total_pages} pages: {filename}")
            return full_text, total_pages
        except Exception as e:
            logging.error(f"[PDF] Extraction failed for {filename}: {e}")
            return "", 0

    # CSV extraction
    if ext == '.csv':
        try:
            import csv
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
            text = "\n".join([", ".join(row) for row in rows])
            return text, len(rows)
        except Exception as e:
            logging.error(f"[CSV] Parse failed for {filename}: {e}")
            return "", 0

    # JSON extraction
    if ext == '.json':
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            text = json.dumps(data, ensure_ascii=False, indent=2)
            return text, 1
        except Exception as e:
            logging.error(f"[JSON] Parse failed for {filename}: {e}")
            return "", 0

    # Plain text (txt, md, py, etc.)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        return text, 1
    except UnicodeDecodeError:
        logging.warning(f"[Extract] Binary file {filename} — cannot extract text")
        return "", 0

def _emit_indexing_progress(job_id, data):
    """Broadcast indexing progress via WebSocket."""
    _indexing_status[job_id] = data
    try:
        socketio_server.emit('indexing_progress', {
            "job_id": job_id,
            **data
        })
    except Exception as e:
        logging.debug(f"Indexing progress emit failed: {e}")

def _chunk_text(text, chunk_size=500, overlap=50):
    """Split text into overlapping chunks."""
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i + chunk_size]
        if chunk.strip():
            chunks.append(chunk.strip())
    return chunks

def _extract_keywords(text):
    """Extract keywords from text for keyword-based search.
    P4: Enhanced Korean language support with stop words and particle stripping.
    """
    import re
    words = re.findall(r'[가-힣a-zA-Z]{2,}', text.lower())
    # P4: Extended stop words for Korean + English
    stop_words = {
        # English
        'the','and','for','are','but','not','you','all','can','had','her','was','one',
        'our','out','day','get','has','him','his','how','its','may','new','now','old',
        'this','that','with','from','have','will','been','they','each','make',
        # Korean particles/postpositions
        '이것','그것','이런','그런','하는','있는','되는','하고','에서','으로','것은',
        '때문','하지','않는','것이','대한','위한','대해','통해','따라','관한',
        '합니다','입니다','습니다','주세요','알려주세요','해주세요',
        '간단한','자세한','싶습니다','있나요','없나요',
        '그리고','하지만','그러나','그래서','따라서','그런데',
    }
    # P4: Korean particle stripping
    _ko_suffixes = [
        '에서는', '에서도', '으로는', '으로도',
        '에서', '에게', '에는', '에도',
        '으로', '이란', '이라', '이며', '이고', '이나',
        '까지', '부터', '마저',
        '에', '을', '를', '이', '가', '은', '는', '의', '와', '과', '로',
    ]
    def _strip_particles(word):
        for s in _ko_suffixes:
            if word.endswith(s) and len(word) > len(s):
                return word[:-len(s)]
        return word

    result = set()
    for w in words:
        if w in stop_words or len(w) < 2:
            continue
        result.add(w)
        stripped = _strip_particles(w)
        if stripped != w and len(stripped) >= 1:
            result.add(stripped)
    return result

# ── RAG Epoch Profiles per File Type ──
RAG_FILE_PROFILES = {
    ".pdf": {
        "label": "PDF Document",
        "epochs": 5,
        "passes": [
            {"chunk_size": 1500, "overlap": 150, "label": "Macro (전체 구조)"},
            {"chunk_size": 1000, "overlap": 100, "label": "Coarse (구조 파악)"},
            {"chunk_size": 500,  "overlap": 80,  "label": "Medium (핵심 내용)"},
            {"chunk_size": 250,  "overlap": 60,  "label": "Fine (상세 검색)"},
            {"chunk_size": 150,  "overlap": 40,  "label": "Ultra-Fine (정밀 분석)"},
        ],
        "keyword_boost": 1.2,
        "description": "PDF는 페이지 구조가 있어 5단계 다단계 청킹으로 최대 커버리지"
    },
    ".txt": {
        "label": "Plain Text",
        "epochs": 4,
        "passes": [
            {"chunk_size": 1200, "overlap": 120, "label": "Macro (전체 맥락)"},
            {"chunk_size": 800,  "overlap": 80,  "label": "Coarse (단락 단위)"},
            {"chunk_size": 400,  "overlap": 60,  "label": "Fine (정밀 검색)"},
            {"chunk_size": 200,  "overlap": 40,  "label": "Micro (문장 단위)"},
        ],
        "keyword_boost": 1.0,
        "description": "텍스트 파일은 4패스로 완전한 커버리지"
    },
    ".md": {
        "label": "Markdown",
        "epochs": 4,
        "passes": [
            {"chunk_size": 1000, "overlap": 100, "label": "Document (문서 단위)"},
            {"chunk_size": 600,  "overlap": 80,  "label": "Section (섹션 단위)"},
            {"chunk_size": 300,  "overlap": 50,  "label": "Paragraph (문단 단위)"},
            {"chunk_size": 150,  "overlap": 30,  "label": "Sentence (문장 단위)"},
        ],
        "keyword_boost": 1.1,
        "description": "마크다운은 섹션 구조 기반 4단계 최적화"
    },
    ".csv": {
        "label": "CSV Data",
        "epochs": 3,
        "passes": [
            {"chunk_size": 1500, "overlap": 150, "label": "Table (테이블 단위)"},
            {"chunk_size": 800,  "overlap": 100, "label": "Row Groups (행 그룹)"},
            {"chunk_size": 400,  "overlap": 50,  "label": "Row Detail (행 상세)"},
        ],
        "keyword_boost": 0.8,
        "description": "CSV는 행 기반 데이터 3단계 분석"
    },
    ".json": {
        "label": "JSON Data",
        "epochs": 4,
        "passes": [
            {"chunk_size": 1200, "overlap": 120, "label": "Root (루트 구조)"},
            {"chunk_size": 800,  "overlap": 100, "label": "Object (객체 단위)"},
            {"chunk_size": 350,  "overlap": 50,  "label": "Field (필드 단위)"},
            {"chunk_size": 180,  "overlap": 30,  "label": "Value (값 단위)"},
        ],
        "keyword_boost": 0.9,
        "description": "JSON은 구조 보존 4단계 분석"
    },
    ".py": {
        "label": "Python Code",
        "epochs": 4,
        "passes": [
            {"chunk_size": 1200, "overlap": 120, "label": "Module (모듈 단위)"},
            {"chunk_size": 800,  "overlap": 100, "label": "Function (함수 단위)"},
            {"chunk_size": 400,  "overlap": 60,  "label": "Block (블록 단위)"},
            {"chunk_size": 200,  "overlap": 30,  "label": "Line (라인 단위)"},
        ],
        "keyword_boost": 1.3,
        "description": "코드는 함수/클래스 4단계 정밀 분석"
    },
    "_default": {
        "label": "Generic",
        "epochs": 4,
        "passes": [
            {"chunk_size": 1000, "overlap": 100, "label": "Macro"},
            {"chunk_size": 600,  "overlap": 80,  "label": "Coarse"},
            {"chunk_size": 300,  "overlap": 50,  "label": "Fine"},
            {"chunk_size": 150,  "overlap": 30,  "label": "Ultra-Fine"},
        ],
        "keyword_boost": 1.0,
        "description": "기본 프로파일 (4단계)"
    }
}

def _get_file_profile(filename, custom_epochs=None):
    """Get the optimal RAG profile for a file type."""
    ext = os.path.splitext(filename)[1].lower()
    profile = RAG_FILE_PROFILES.get(ext, RAG_FILE_PROFILES["_default"]).copy()
    if custom_epochs is not None and custom_epochs > 0:
        # Scale passes to custom epoch count
        base_passes = profile["passes"]
        if custom_epochs <= len(base_passes):
            profile["passes"] = base_passes[:custom_epochs]
        else:
            # Add extra fine-grained passes for higher epochs
            profile["passes"] = list(base_passes)
            for extra in range(custom_epochs - len(base_passes)):
                last = base_passes[-1]
                profile["passes"].append({
                    "chunk_size": max(100, last["chunk_size"] - (extra + 1) * 50),
                    "overlap": max(20, last["overlap"] + 10),
                    "label": f"Ultra-Fine (패스 {len(base_passes) + extra + 1})"
                })
        profile["epochs"] = custom_epochs
    return profile

def _compute_chunk_quality(chunk, keywords, keyword_boost=1.0):
    """Compute quality score for a chunk (0-100)."""
    if not chunk.strip():
        return 0
    length_score = min(len(chunk) / 200, 1.0) * 30  # up to 30 for length
    keyword_count = len(keywords)
    keyword_score = min(keyword_count / 8, 1.0) * 40 * keyword_boost  # up to 40 for keywords
    # Diversity: unique chars ratio
    unique_ratio = len(set(chunk)) / max(len(chunk), 1)
    diversity_score = unique_ratio * 30  # up to 30 for diversity
    return min(round(length_score + keyword_score + diversity_score), 100)

def _search_knowledge(team_name, query, top_k=3):
    """Keyword-based knowledge search with quality-weighted scoring.
    P2: Uses shared chunk pool instead of per-team copies.
    P4: Enhanced Korean keyword extraction.
    """
    # P2: Collect chunks from shared pool based on team's file list
    team_file_list = _team_files.get(team_name, [])
    chunks = []
    for fname in team_file_list:
        chunks.extend(_shared_chunks.get(fname, []))
    # Also check legacy per-team storage for backward compatibility
    chunks.extend(_knowledge_chunks.get(team_name, []))

    if not chunks:
        return []
    query_keywords = _extract_keywords(query)
    scored = []
    for chunk_data in chunks:
        keyword_overlap = len(query_keywords & chunk_data.get("keywords", set()))
        if keyword_overlap > 0:
            quality = chunk_data.get("quality", 50)
            score = keyword_overlap * (1 + quality / 100)
            scored.append((score, chunk_data["chunk"]))
    scored.sort(key=lambda x: -x[0])
    return [s[1] for s in scored[:top_k]]

def _index_knowledge_file(team_name, filename, content, custom_epochs=None, job_id=None):
    """Multi-epoch adaptive RAG indexing with per-file optimization."""
    if team_name not in _knowledge_chunks:
        _knowledge_chunks[team_name] = []
    # Remove old chunks from same file
    _knowledge_chunks[team_name] = [c for c in _knowledge_chunks[team_name] if c.get("source") != filename]

    profile = _get_file_profile(filename, custom_epochs)
    all_chunks_set = set()  # deduplication
    total_added = 0
    epoch_results = []

    for epoch_idx, pass_config in enumerate(profile["passes"]):
        chunk_size = pass_config["chunk_size"]
        overlap_val = pass_config["overlap"]
        pass_label = pass_config["label"]

        # Emit progress per epoch
        if job_id:
            _emit_indexing_progress(job_id, {
                "phase": "epoch",
                "progress": int((epoch_idx / len(profile["passes"])) * 100),
                "current_file": filename,
                "message": f"🔄 Epoch {epoch_idx+1}/{len(profile['passes'])}: {pass_label} (chunk={chunk_size}, overlap={overlap_val})",
                "epoch": epoch_idx + 1,
                "total_epochs": len(profile["passes"]),
                "pass_label": pass_label,
                "files_status": []
            })

        raw_chunks = _chunk_text(content, chunk_size=chunk_size, overlap=overlap_val)
        epoch_added = 0

        for chunk in raw_chunks:
            chunk_hash = hash(chunk[:100] + chunk[-100:]) if len(chunk) > 200 else hash(chunk)
            if chunk_hash in all_chunks_set:
                continue
            all_chunks_set.add(chunk_hash)

            keywords = _extract_keywords(chunk)
            quality = _compute_chunk_quality(chunk, keywords, profile.get("keyword_boost", 1.0))

            _knowledge_chunks[team_name].append({
                "source": filename,
                "chunk": chunk,
                "keywords": keywords,
                "quality": quality,
                "epoch": epoch_idx + 1,
                "pass_label": pass_label,
                "chunk_size": chunk_size,
            })
            epoch_added += 1

        epoch_results.append({
            "epoch": epoch_idx + 1,
            "label": pass_label,
            "chunk_size": chunk_size,
            "overlap": overlap_val,
            "chunks_generated": len(raw_chunks),
            "chunks_added": epoch_added,
            "deduplicated": len(raw_chunks) - epoch_added,
        })
        total_added += epoch_added
        logging.info(f"[RAG Epoch {epoch_idx+1}] {filename}: {pass_label} -> {epoch_added} chunks (dedup: {len(raw_chunks) - epoch_added})")

    # Compute aggregate quality
    file_chunks = [c for c in _knowledge_chunks[team_name] if c.get("source") == filename]
    avg_quality = sum(c.get("quality", 0) for c in file_chunks) / max(len(file_chunks), 1)

    # Store epoch metadata
    _indexing_status[f"epoch_{team_name}_{filename}"] = {
        "profile": profile["label"],
        "epochs_run": len(profile["passes"]),
        "total_chunks": total_added,
        "avg_quality": round(avg_quality, 1),
        "epoch_results": epoch_results,
        "keyword_boost": profile.get("keyword_boost", 1.0),
    }

    # ── Bridge to Brain Graph ──
    # Auto-create brain nodes from indexed knowledge so they appear in the 뇌 그래프
    try:
        from chatdev.brain_knowledge import add_knowledge as _brain_add, link_knowledge as _brain_link, get_brain_graph as _brain_get
        existing_graph = _brain_get()
        existing_titles = {n.get("title", "") for n in existing_graph.get("nodes", [])}

        # Skip if this file is already in the brain graph
        book_title = os.path.splitext(filename)[0]
        if book_title not in existing_titles:
            # 1) Create a source/book node for the file
            ext = os.path.splitext(filename)[1].lower()
            source_node = _brain_add(
                title=book_title,
                content=f"학습된 문서: {filename} ({total_added}개 청크, 품질: {round(avg_quality, 1)})",
                node_type="experience",
                tags=[team_name, ext.replace(".", ""), "auto-indexed"],
                source=f"rag-{team_name}",
                importance=min(3, max(1, total_added // 15)),
            )
            source_id = source_node.get("id", "")

            # 2) Extract top concepts from chunks as child nodes
            all_keywords = {}
            for c in file_chunks:
                for kw in c.get("keywords", set()):
                    if len(kw) >= 2:
                        all_keywords[kw] = all_keywords.get(kw, 0) + 1

            # Take top N most-frequent keywords as concept nodes
            top_concepts = sorted(all_keywords.items(), key=lambda x: -x[1])[:12]
            for concept_name, freq in top_concepts:
                if concept_name in existing_titles:
                    continue
                concept_node = _brain_add(
                    title=concept_name,
                    content=f"'{book_title}'에서 추출된 핵심 개념 (빈도: {freq}회)",
                    node_type="concept",
                    tags=[book_title[:20], "auto-extracted"],
                    source=f"rag-{team_name}",
                    importance=min(3, max(1, freq // 3)),
                )
                if source_id and concept_node.get("id"):
                    _brain_link(source_id, concept_node["id"], "contains", "solid")

            logging.info(f"[Brain Bridge] '{filename}' → 뇌 그래프에 {1 + len(top_concepts)}개 노드 추가")
    except Exception as brain_err:
        logging.debug(f"[Brain Bridge] Skipped: {brain_err}")

    return total_added

# ═══════════════════════════════════════════
#  P2: Shared Chunk Pool — 5x memory savings
# ═══════════════════════════════════════════
_shared_chunks = {}   # { filename: [ {chunk, keywords, quality, ...} ] }
_team_files = {}      # { team_name: [filename1, filename2, ...] }
_indexing_ready = False  # True when background indexing completes

# ═══════════════════════════════════════════
#  P3: File Hash Caching — skip unchanged files
# ═══════════════════════════════════════════
_INDEX_CACHE_FILE = os.path.join(VISUALIZER_DIR, "data", "index_cache.json")

def _load_index_cache():
    """Load file hash cache from disk."""
    try:
        if os.path.exists(_INDEX_CACHE_FILE):
            with open(_INDEX_CACHE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logging.debug(f"[IndexCache] Load error: {e}")
    return {}

def _save_index_cache(cache):
    """Save file hash cache to disk."""
    try:
        os.makedirs(os.path.dirname(_INDEX_CACHE_FILE), exist_ok=True)
        with open(_INDEX_CACHE_FILE, "w") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception as e:
        logging.debug(f"[IndexCache] Save error: {e}")

def _get_file_hash(filepath):
    """Compute MD5 hash of a file for change detection."""
    import hashlib
    h = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                h.update(block)
        return h.hexdigest()
    except Exception:
        return None

def _pre_index_existing_knowledge():
    """Scan CompanyConfig/Knowledge/ and auto-index documents for default teams.
    P1: Runs in background thread.
    P2: Uses shared chunk pool (files indexed once, referenced by all teams).
    P3: Uses file hash caching (skip unchanged files on restart).
    """
    global _indexing_ready
    supported_exts = ('.md', '.txt', '.pdf', '.csv', '.json', '.py', '.html', '.xml', '.yaml', '.yml')
    try:
        root_dir = ROOT_DIR  # #4: Use constant
        knowledge_dir = os.path.join(root_dir, "CompanyConfig", "Knowledge")
        if not os.path.exists(knowledge_dir):
            _indexing_ready = True
            return
        files = [f for f in os.listdir(knowledge_dir) if os.path.isfile(os.path.join(knowledge_dir, f)) and f.lower().endswith(supported_exts)]
        default_teams = ["Squad_A", "Development_Team", "Marketing_Team", "Design_Team", "Tech_Squad"]

        # P3: Load hash cache
        cache = _load_index_cache()
        cache_changed = False

        for fname in files:
            fpath = os.path.join(knowledge_dir, fname)
            try:
                # P3: Check if file has changed
                file_hash = _get_file_hash(fpath)
                if file_hash and cache.get(fname) == file_hash and fname in _shared_chunks:
                    logging.info(f"[PreIndex] ⏩ Cache hit: '{fname}' (skipped)")
                    continue

                content, _ = _extract_text_from_file(fpath, fname)
                if not content.strip():
                    continue

                # P2: Index once into shared pool (not per-team)
                _index_knowledge_file("_shared", fname, content)

                # Move chunks from _shared to shared pool
                if "_shared" in _knowledge_chunks:
                    _shared_chunks[fname] = _knowledge_chunks.pop("_shared", [])

                # P2: Register file for all teams (reference only, no duplication)
                for team in default_teams:
                    if team not in _team_files:
                        _team_files[team] = []
                    if fname not in _team_files[team]:
                        _team_files[team].append(fname)
                    if team not in squad_injected_knowledge:
                        squad_injected_knowledge[team] = []
                    if fname not in squad_injected_knowledge[team]:
                        squad_injected_knowledge[team].append(fname)

                # P3: Update cache
                if file_hash:
                    cache[fname] = file_hash
                    cache_changed = True

                logging.info(f"[PreIndex] ✅ Indexed '{fname}' ({len(content)} chars, {len(_shared_chunks.get(fname, []))} chunks)")
            except Exception as _e:
                logging.debug(f"[suppressed] Exception: {_e}")

        # P3: Save cache if changed
        if cache_changed:
            _save_index_cache(cache)
            logging.info(f"[PreIndex] 💾 Index cache saved ({len(cache)} files)")

    except Exception as _e:
        logging.debug(f"[suppressed] Exception: {_e}")

    _indexing_ready = True
    logging.info(f"[PreIndex] 🎉 Background indexing complete — {len(_shared_chunks)} files, {sum(len(v) for v in _shared_chunks.values())} total chunks")

# P1: Run pre-indexing in background thread (server starts immediately!)
import threading
_indexer_thread = threading.Thread(
    target=_pre_index_existing_knowledge,
    daemon=True,
    name="knowledge-bg-indexer"
)
_indexer_thread.start()
logging.info("🚀 [PreIndex] Background indexing started — server is ready immediately!")

try:
    from chatdev.rag_pipeline import RAGMemoryPipeline
except ImportError:
    RAGMemoryPipeline = None

_gdrive_tokens = {}
_SANDBOX_MODE = not (
    bool(os.environ.get("GOOGLE_CLIENT_ID"))
    and bool(os.environ.get("GOOGLE_CLIENT_SECRET"))
    and "your_" not in os.environ.get("GOOGLE_CLIENT_ID", "")
    and "your_" not in os.environ.get("GOOGLE_CLIENT_SECRET", "")
)

if _SANDBOX_MODE:
    _gdrive_tokens["default"] = {
        "access_token": "SANDBOX_TOKEN_INIT",
        "refresh_token": "SANDBOX_REFRESH",
        "expires_in": 999999,
        "connected_at": datetime.now().isoformat(),
        "sandbox": True
    }


# ==========================================
#    ⚙️  AI Multi-Engine Switching Router
#    Delegated to visualizer.llm_client (#1)
# ==========================================
from visualizer.llm_client import (
    get_llm_response, get_ai_config, set_ai_config,
    persist_ai_config_to_env, PROVIDER_MODELS,
)
from visualizer.llm_client import _AI_ENGINE_CONFIG, PROVIDER_MODELS as _PROVIDER_MODELS

# Backward-compatible alias
_persist_ai_config_to_env = persist_ai_config_to_env


_SANDBOX_DRIVE_FILES = [
    {"id": "gdoc_001", "name": "📋 Company OKR 2026 Q2", "mimeType": "application/vnd.google-apps.document", "size": "24 KB", "modifiedTime": "2026-05-28T09:00:00Z", "webViewLink": "#"},
    {"id": "gdoc_002", "name": "📊 Product Requirements Doc (PRD) v3.1", "mimeType": "application/vnd.google-apps.document", "size": "67 KB", "modifiedTime": "2026-05-25T14:30:00Z", "webViewLink": "#"},
    {"id": "gsheet_001", "name": "📈 Revenue Model FY2026", "mimeType": "application/vnd.google-apps.spreadsheet", "size": "12 KB", "modifiedTime": "2026-05-29T11:15:00Z", "webViewLink": "#"},
    {"id": "gdoc_003", "name": "🔒 Internal API Specification v2.0", "mimeType": "application/vnd.google-apps.document", "size": "89 KB", "modifiedTime": "2026-05-20T08:45:00Z", "webViewLink": "#"},
    {"id": "gdoc_004", "name": "📖 Employee Handbook & Security Policy", "mimeType": "application/vnd.google-apps.document", "size": "41 KB", "modifiedTime": "2026-05-15T16:00:00Z", "webViewLink": "#"},
    {"id": "gdoc_005", "name": "🏗️ Tech Stack Architecture Decision Record", "mimeType": "application/vnd.google-apps.document", "size": "33 KB", "modifiedTime": "2026-05-22T13:20:00Z", "webViewLink": "#"},
]

# Sandbox mock file contents (for grounding injection)
_SANDBOX_CONTENTS = {
    "gdoc_001": "Company OKR 2026 Q2:\n\nObjective 1: Launch AI Workforce Platform v2.0\n- KR1: Deploy multi-agent orchestration to 50 enterprise clients\n- KR2: Achieve 99.9% uptime SLA\n- KR3: Reduce agent response latency to under 200ms\n\nObjective 2: Expand Knowledge Grounding Infrastructure\n- KR1: Integrate Google Drive, Notion, and Confluence\n- KR2: Support 100+ concurrent document sources per team\n- KR3: Implement real-time RAG with sub-second retrieval",
    "gdoc_002": "Product Requirements Document (PRD) v3.1\n\n1. Executive Summary\nBuild a visual drag-and-drop AI agent workflow builder with enterprise-grade security, multi-tenant isolation, and NotebookLM-style knowledge grounding.\n\n2. User Stories\n- As a founder, I want to drag agents onto a canvas and connect them freely\n- As a team lead, I want to inject company documents as grounding sources\n- As a developer, I want each agent to have customizable system prompts and MCP tool bindings\n\n3. Technical Requirements\n- UUID-based node instances for unlimited agent duplication\n- Freeform graph edges (source/target pairs, no tree hierarchy)\n- Auto-save graph state to backend JSON storage\n- Google Drive OAuth 2.0 integration with Drive Picker API",
    "gsheet_001": "Revenue Model FY2026:\n\nQ1 Revenue: $2.4M (Actual)\nQ2 Revenue: $3.8M (Projected)\nQ3 Revenue: $5.2M (Target)\nQ4 Revenue: $7.1M (Target)\n\nARR Target: $18.5M\nMonthly Active Enterprise Users: 1,200\nAgent Executions per Day: 45,000\nAverage Revenue per User: $15,417/year",
    "gdoc_003": "Internal API Specification v2.0\n\nBase URL: https://api.chatdev-platform.io/v2\n\nAuthentication: Bearer token (JWT)\nRate Limit: 1000 req/min per tenant\n\nEndpoints:\n- POST /agents/create — Create new agent instance\n- GET /agents/:id — Get agent details\n- POST /workflows/execute — Execute agent workflow\n- GET /knowledge/sources — List knowledge sources\n- POST /knowledge/ground — Inject grounding context\n\nWebSocket: wss://ws.chatdev-platform.io/stream\nEvents: agent.started, agent.completed, agent.error, workflow.progress",
    "gdoc_004": "Employee Handbook & Security Policy\n\nSection 7: Data Security\n- All API keys must be stored in encrypted vaults\n- No plaintext credentials in source code repositories\n- Multi-factor authentication required for all production systems\n- Data classification: Public, Internal, Confidential, Restricted\n\nSection 12: AI Agent Governance\n- All agent system prompts must be reviewed before deployment\n- Maximum token budget: 10,000 tokens per agent per task\n- External API calls require security team approval\n- Agent outputs must be logged for audit compliance",
    "gdoc_005": "Tech Stack Architecture Decision Record\n\nFrontend: HTML5 + D3.js + jQuery (Enterprise White Monochrome Theme)\nBackend: Python Flask + SocketIO\nDatabase: JSON file storage (Phase 1) → PostgreSQL (Phase 2)\nAI Runtime: OpenAI GPT-4o / Claude 3.5 via MCP\nKnowledge: RAG with chunk-based vector retrieval\nDeployment: Gunicorn + Nginx (Production)\nMonitoring: Custom health endpoints + Prometheus metrics\nSecurity: AES-256 encrypted API key vault, OAuth 2.0 for external services",
}

executive_states = persistent_executive_states if _PERSISTENT_STATE else {}

_ROLE_KEYWORDS = {
    "Programmer": ["코딩", "개발", "프로그래", "코드", "code", "develop", "program", "engineer", "build", "구현"],
    "Designer": ["디자인", "design", "UI", "UX", "화면", "레이아웃", "시각"],
    "Content Writer": ["카피", "콘텐츠", "글", "문서", "write", "copy", "content", "작성", "블로그", "기사"],
    "Tester": ["테스트", "QA", "검증", "test", "verify", "품질"],
    "Data Analyst": ["데이터", "분석", "data", "analy", "통계", "리포트", "report", "지표"],
    "Reviewer": ["리뷰", "검수", "review", "피드백", "feedback", "교정"],
    "DevOps": ["배포", "deploy", "인프라", "서버", "CI", "CD", "ops", "운영"],
    "Chief Executive Officer": ["총괄", "CEO", "리더", "관리", "매니저", "manage", "lead", "기획"],
    "Chief Product Officer": ["기획", "product", "PRD", "요구사항", "스펙", "전략", "strategy"],
    "Creative Director": ["크리에이티브", "creative", "마케팅", "marketing", "광고", "브랜드", "brand", "SNS", "슬랙", "slack"],
}

# Workflow template patterns
_WORKFLOW_TEMPLATES = {
    "marketing": {
        "keywords": ["marketing", "마케팅", "광고", "브랜드", "SNS", "카피"],
        "description": "마케팅 자동화 라인",
        "nodes": ["Chief Product Officer", "Content Writer", "Designer", "Creative Director", "Reviewer"],
        "edges": [(0,1), (0,2), (1,3), (2,3), (3,4)]
    },
    "development": {
        "keywords": ["development", "개발", "코딩", "프로그래", "소프트웨어", "빌드"],
        "description": "소프트웨어 개발 파이프라인",
        "nodes": ["Chief Product Officer", "Programmer", "Designer", "Tester", "Reviewer", "DevOps"],
        "edges": [(0,1), (0,2), (1,3), (2,3), (3,4), (4,5)]
    },
    "analysis": {
        "keywords": ["analysis", "분석", "데이터", "리포트", "통계", "지표"],
        "description": "데이터 분석 워크플로우",
        "nodes": ["Chief Executive Officer", "Data Analyst", "Content Writer", "Reviewer"],
        "edges": [(0,1), (1,2), (2,3)]
    },
    "content": {
        "keywords": ["content", "콘텐츠", "블로그", "기사", "문서", "작성"],
        "description": "콘텐츠 제작 파이프라인",
        "nodes": ["Chief Product Officer", "Content Writer", "Designer", "Reviewer", "Creative Director"],
        "edges": [(0,1), (0,2), (1,3), (2,3), (3,4)]
    }
}

_active_schedules = {}

def ensure_and_load_graph(team_name):
    """#3: Loads freeform graph for a team. ChatChainConfig.json is Source of Truth;
    freeform_graphs/ serves as a runtime view cache with UI layout (x/y coords).
    If graph cache is missing or incomplete, auto-seeds from ChatChainConfig.json.
    
    Architecture (#3):
        ChatChainConfig.json → Authoritative definition (roles, nodes, edges)
        freeform_graphs/{team}.json → UI cache (x/y positions, auto_seeded flags)
    """
    # #20: Use team-level lock for thread-safe graph operations
    lock = get_team_lock(team_name)
    with lock:
        graph_dir = os.path.join(VISUALIZER_DIR, "freeform_graphs")
        os.makedirs(graph_dir, exist_ok=True)
        graph_path = os.path.join(graph_dir, f"{team_name}.json")

    saved_nodes = []
    saved_edges = []
    gd = {}
    if os.path.exists(graph_path):
        try:
            with open(graph_path, 'r', encoding='utf-8') as f:
                gd = json.load(f)
            saved_nodes = gd.get("nodes", [])
            saved_edges = gd.get("edges", [])
        except Exception as _e:
            logging.debug(f"[ensure_and_load_graph] Error reading graph: {_e}")

    # Load actual roster from ChatChainConfig
    root_dir = ROOT_DIR  # #4: Use constant
    chain_path = os.path.join(root_dir, "CompanyConfig", "Teams", team_name, "ChatChainConfig.json")
    
    roster_roles = []
    if os.path.exists(chain_path):
        try:
            with open(chain_path, 'r', encoding='utf-8') as f:
                chain_data = json.load(f)
            for node in chain_data.get("nodes", []):
                if node.get("id") == "Trigger":
                    continue
                assignee = node.get("assignee", node.get("id", ""))
                if assignee:
                    roster_roles.append(assignee)
            for role in chain_data.get("recruitments", []):
                roster_roles.append(role)
        except Exception as _e:
            logging.debug(f"[ensure_and_load_graph] Error reading chain: {_e}")
    else:
        # Fallback default roster
        roster_roles = ["Chief Executive Officer", "Programmer", "Code Reviewer"]

    # Auto-merge logic
    existing_roles = set()
    for n in saved_nodes:
        existing_roles.add(n.get("role", ""))
        existing_roles.add(n.get("title", ""))

    import math, random
    new_nodes_added = False
    center_x, center_y = 450, 300
    
    missing_roles = [r for r in roster_roles if r not in existing_roles]
    total_to_place = len(missing_roles)
    placed = 0

    for role in roster_roles:
        if role in existing_roles:
            continue
        uid = role.replace(" ", "_").lower() + "_" + ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=6))
        
        angle = (2 * math.pi * placed) / max(total_to_place, 1) - math.pi / 2
        radius = 200 + (placed % 2) * 60
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        
        saved_nodes.append({
            "id": uid,
            "role": role,
            "title": role,
            "x": round(x),
            "y": round(y),
            "details": {"title": role},
            "auto_seeded": True
        })
        
        if len(saved_nodes) > 1 and placed > 0:
            leader_id = saved_nodes[0]["id"]
            saved_edges.append({
                "id": f"edge_{uid}_{leader_id}",
                "source": leader_id,
                "target": uid
            })
        
        existing_roles.add(role)
        placed += 1
        new_nodes_added = True

    # Save graph if file was missing or new nodes were added
    if new_nodes_added or not os.path.exists(graph_path):
        gd["team_name"] = team_name
        gd["nodes"] = saved_nodes
        gd["edges"] = saved_edges
        gd["saved_at"] = datetime.now().isoformat()
        if new_nodes_added:
            gd["auto_merged"] = True
        try:
            with open(graph_path, 'w', encoding='utf-8') as f:
                json.dump(gd, f, indent=2, ensure_ascii=False)
        except Exception as _e:
            logging.error(f"[ensure_and_load_graph] Error writing graph file: {_e}")

    return saved_nodes, saved_edges

def _topological_sort(nodes, edges):
    """#2: Delegate to unified topological sort in workflow_utils."""
    return unified_topological_sort(nodes, edges)

# ==========================================
#    Celery + Redis Worker & Live Log APIs
# ==========================================
from visualizer.celery_worker import (
    WORKER_MODE, emit_log, get_logs, get_metering_summary,
    meter_action, execute_workflow_background,
    get_background_tasks, start_recurring_schedule, stop_recurring_schedule,
    run_alignment_meeting, get_alignment_session, execute_subtasks_background,
    _CELERY_AVAILABLE, _REDIS_AVAILABLE
)

# ── Pipeline Governance Engine Import ──
_GOVERNANCE_ENGINE_OK = False
try:
    from visualizer.pipeline_governance import (
        HITLGateway, ApprovalStatus, GateType,
        resource_governor, get_all_contracts, update_contract,
        create_job_context, get_job_context,
    )
    _GOVERNANCE_ENGINE_OK = True
    logging.info("✅ [Governance] Pipeline Governance Engine loaded")
except Exception as _gov_import_err:
    logging.warning(f"[Governance] Engine not loaded: {_gov_import_err}")


# ==========================================
#    Governance API — HITL, Budget, Contracts
# ==========================================

_UPLOAD_DIR = os.path.join(VISUALIZER_DIR, "..", "WareHouse", "_uploads")
os.makedirs(_UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "svg"}

@socketio_server.on("subscribe_logs")
def handle_subscribe_logs(data):
    """Client subscribes to live log streaming."""
    room = data.get("team_name", "Squad_A")
    join_room(f"logs_{room}")
    emit("log_subscribed", {"room": f"logs_{room}", "status": "subscribed"})
    logging.info(f"📡 [LiveLog] Client subscribed to logs_{room}")

# Periodic log broadcast (push latest logs to subscribers)
def _log_broadcaster():
    """Background thread that broadcasts new logs via WebSocket."""
    last_count = 0
    while True:
        time.sleep(1)
        current_logs = get_logs(10)
        if len(current_logs) != last_count and current_logs:
            last_count = len(current_logs)
            try:
                summary = get_metering_summary()
                socketio_server.emit("live_log", {
                    "logs": current_logs[-5:],
                    "billing": {
                        "total_cost_usd": summary["total_cost_usd"],
                        "total_actions": summary["total_actions"]
                    }
                })
            except Exception as _e:
                logging.debug(f"[suppressed] Exception: {_e}")

import threading as _threading
_log_broadcast_thread = _threading.Thread(target=_log_broadcaster, daemon=True)
_log_broadcast_thread.start()

# ==========================================
#          Freeform Graph APIs (Matrix Network)
# ==========================================

TEAM_TEMPLATES = {
    "instagram": {
        "name": "Instagram Content Team",
        "agents": [
            {"id": "Content_Strategist", "phase": "ContentStrategy", "phaseType": "SimplePhase", "role": "콘텐츠 전략가", "max_turn_step": 1, "need_reflect": "False"},
            {"id": "Copywriter", "phase": "Copywriting", "phaseType": "SimplePhase", "role": "카피라이터", "max_turn_step": 1, "need_reflect": "False"},
            {"id": "Visual_Designer", "phase": "VisualDesign", "phaseType": "SimplePhase", "role": "비주얼 디자이너", "max_turn_step": 1, "need_reflect": "False"},
            {"id": "Hashtag_Analyst", "phase": "HashtagAnalysis", "phaseType": "SimplePhase", "role": "해시태그 분석가", "max_turn_step": -1, "need_reflect": "True"},
        ]
    },
    "youtube": {
        "name": "YouTube Production Team",
        "agents": [
            {"id": "Trend_Researcher", "phase": "TrendResearch", "phaseType": "SimplePhase", "role": "트렌드 리서처", "max_turn_step": -1, "need_reflect": "True"},
            {"id": "Script_Writer", "phase": "ScriptWriting", "phaseType": "SimplePhase", "role": "대본 작가", "max_turn_step": 1, "need_reflect": "False"},
            {"id": "Thumbnail_Designer", "phase": "ThumbnailDesign", "phaseType": "SimplePhase", "role": "썸네일 디자이너", "max_turn_step": 1, "need_reflect": "False"},
            {"id": "SEO_Optimizer", "phase": "SEOOptimization", "phaseType": "SimplePhase", "role": "SEO 최적화 전문가", "max_turn_step": -1, "need_reflect": "False"},
        ]
    },
    "development": {
        "name": "Software Development Team",
        "agents": [
            {"id": "Architect", "phase": "Architecture", "phaseType": "SimplePhase", "role": "소프트웨어 아키텍트", "max_turn_step": 1, "need_reflect": "True"},
            {"id": "Frontend_Dev", "phase": "FrontendDev", "phaseType": "SimplePhase", "role": "프론트엔드 개발자", "max_turn_step": 1, "need_reflect": "False"},
            {"id": "Backend_Dev", "phase": "BackendDev", "phaseType": "SimplePhase", "role": "백엔드 개발자", "max_turn_step": 1, "need_reflect": "False"},
            {"id": "QA_Engineer", "phase": "QATesting", "phaseType": "SimplePhase", "role": "QA 엔지니어", "max_turn_step": -1, "need_reflect": "True"},
        ]
    },
    "marketing": {
        "name": "Digital Marketing Team",
        "agents": [
            {"id": "Market_Analyst", "phase": "MarketAnalysis", "phaseType": "SimplePhase", "role": "시장 분석가", "max_turn_step": -1, "need_reflect": "True"},
            {"id": "Ad_Copywriter", "phase": "AdCopywriting", "phaseType": "SimplePhase", "role": "광고 카피라이터", "max_turn_step": 1, "need_reflect": "False"},
            {"id": "Growth_Hacker", "phase": "GrowthHacking", "phaseType": "SimplePhase", "role": "그로스 해커", "max_turn_step": 1, "need_reflect": "False"},
            {"id": "Report_Generator", "phase": "ReportGeneration", "phaseType": "SimplePhase", "role": "리포트 생성기", "max_turn_step": -1, "need_reflect": "False"},
        ]
    },
    "customer_success": {
        "name": "Customer Success Team",
        "agents": [
            {"id": "Ticket_Triage", "phase": "TicketTriage", "phaseType": "SimplePhase", "role": "티켓 분류기", "max_turn_step": -1, "need_reflect": "True"},
            {"id": "Solution_Engineer", "phase": "SolutionEngineering", "phaseType": "SimplePhase", "role": "솔루션 엔지니어", "max_turn_step": 1, "need_reflect": "False"},
            {"id": "Satisfaction_Surveyor", "phase": "SatisfactionSurvey", "phaseType": "SimplePhase", "role": "만족도 조사관", "max_turn_step": 1, "need_reflect": "False"},
            {"id": "Escalation_Manager", "phase": "EscalationMgmt", "phaseType": "SimplePhase", "role": "에스컬레이션 매니저", "max_turn_step": -1, "need_reflect": "False"},
        ]
    }
}

PLAYBOOKS_DIR = os.path.join(COMPANY_CONFIG_DIR, "Playbooks")
os.makedirs(PLAYBOOKS_DIR, exist_ok=True)

def _load_playbooks():
    """#3: Load playbooks from external JSON files (hot-reload without restart)."""
    playbooks = {}
    default_path = os.path.join(PLAYBOOKS_DIR, "default_playbooks.json")
    
    # Load default playbooks
    if os.path.exists(default_path):
        try:
            with open(default_path, 'r', encoding='utf-8') as f:
                playbooks = json.load(f)
        except Exception as e:
            logging.error(f"[Playbooks] Failed to load defaults: {e}")
    
    # Load additional custom playbook files
    for fname in glob.glob(os.path.join(PLAYBOOKS_DIR, "*.json")):
        if os.path.basename(fname) == "default_playbooks.json":
            continue
        try:
            with open(fname, 'r', encoding='utf-8') as f:
                custom = json.load(f)
                # Validate: playbook files must be dict-of-dicts (id → {nodes, edges, ...})
                # Skip non-playbook JSON files (e.g. seminar_prompt.json)
                if not isinstance(custom, dict):
                    continue
                has_playbook_shape = any(
                    isinstance(v, dict) and ("nodes" in v or "edges" in v or "trigger" in v)
                    for v in custom.values()
                )
                if not has_playbook_shape:
                    logging.debug(f"[Playbooks] Skipped non-playbook file: {os.path.basename(fname)}")
                    continue
                playbooks.update(custom)
        except Exception as e:
            logging.warning(f"[Playbooks] Skipped {fname}: {e}")
    
    return playbooks

# Initial load (will be re-read on each API call for hot-reload)
PLAYBOOKS = _load_playbooks()

@socketio_server.on('connect')
def handle_connect():
    """Triggered on connect. Browser joins default room 'Squad_A' by default."""
    join_room('Squad_A')
    emit('initial_messages', messages.get('Squad_A', []))

@socketio_server.on('join_team_room')
def handle_join_team_room(data):
    """Bridges client room-switching. Dispatches historical logs filtered by squad."""
    team_name = data.get("team_name", "Squad_A")
    
    # Leave all previous rooms to prevent cross-team log leaks
    client_rooms = rooms()
    for rm in client_rooms:
        if rm != request.sid:
            leave_room(rm)
            
    join_room(team_name)
    emit('initial_messages', messages.get(team_name, []))

@socketio_server.on('client_message')
def handle_client_message(data):
    """Triggered when ChatDev engine sends a message."""
    role = data.get("role")
    text = data.get("text")
    team_name = data.get("team_name", "Squad_A")
    
    # If run has completed, decrement active and increment completed
    if role == "System" and "completed" in text.lower():
        if team_name in squad_stats:
            squad_stats[team_name]["active_tasks"] = max(0, squad_stats[team_name]["active_tasks"] - 1)
            squad_stats[team_name]["completed_tasks"] += 1
            
            # Add to throughput dates
            today = datetime.now().strftime("%m-%d")
            found = False
            for t_item in squad_stats[team_name]["throughput"]:
                if t_item["date"] == today:
                    t_item["count"] += 1
                    found = True
                    break
            if not found:
                squad_stats[team_name]["throughput"].append({"date": today, "count": 1})
            
            # Recalculate cost efficiency
            cost = squad_stats[team_name].get("token_cost", 0.0)
            squad_stats[team_name]["cost_efficiency"] = squad_stats[team_name]["completed_tasks"] / (cost + 0.0001)
            save_squad_stats()
            
            # Broadcast global stats update
            socketio_server.emit('global_stats_update', {"team_name": team_name})
            
    avatarUrl = find_avatar_url(role)
    message = {"role": role, "text": text, "avatarUrl": avatarUrl}
    
    if team_name not in messages:
        messages[team_name] = deque(maxlen=MAX_MESSAGES_PER_TEAM)  # #24: Bounded deque
    messages[team_name].append(message)
    
    emit('new_message', message, room=team_name)

def find_avatar_url(role):
    role = role.replace(" ", "%20")
    avatar_filename = f"avatars/{role}.png"
    avatar_url = f"/static/{avatar_filename}"
    return avatar_url

# ==========================================
#          Real-Time Live Stats Streamer
# ==========================================
import threading
import time
import random


def start_stats_broadcaster():
    def broadcast_loop():
        while True:
            try:
                time.sleep(1.0)
                
                # Dynamic mock telemetry generation to keep dashboard alive & ticking!
                for team_name, stats in squad_stats.items():
                    # 5% chance to start new task if we have 0 active
                    if stats.get("active_tasks", 0) == 0 and random.random() < 0.05:
                        stats["active_tasks"] = random.randint(1, 2)
                    
                    # If there's an active task, mock incremental token cost and workload
                    if stats.get("active_tasks", 0) > 0:
                        # Tick up cumulative token cost
                        cost_inc = random.uniform(0.0001, 0.0006)
                        stats["token_cost"] = stats.get("token_cost", 0.0) + cost_inc
                        
                        # Increment workload calls for a random employee in squad
                        workload = stats.setdefault("workload", {})
                        if workload:
                            active_roles = list(workload.keys())
                        else:
                            active_roles = ["Chief Executive Officer", "Chief Product Officer", "Chief Technology Officer", "Programmer", "Code Reviewer", "Software Test Engineer"]
                        
                        random_role = random.choice(active_roles)
                        workload[random_role] = workload.get(random_role, 0) + random.randint(1, 2)
                        
                        # 8% chance to complete an active task and log throughput
                        if random.random() < 0.08:
                            stats["active_tasks"] = max(0, stats["active_tasks"] - 1)
                            stats["completed_tasks"] = stats.get("completed_tasks", 0) + 1
                            
                            # Log to throughput dates
                            today = datetime.datetime.now().strftime("%m-%d")
                            found = False
                            for t_item in stats.setdefault("throughput", []):
                                if t_item["date"] == today:
                                    t_item["count"] += 1
                                    found = True
                                    break
                            if not found:
                                stats["throughput"].append({"date": today, "count": 1})
                                
                    # Recalculate cost efficiency
                    completed = stats.get("completed_tasks", 0)
                    cost = stats.get("token_cost", 0.0)
                    stats["cost_efficiency"] = completed / (cost + 0.0001)
                    
                    # Emit live stream specific to the squad room
                    socketio_server.emit('live_analytics_stream', {
                        "team_name": team_name,
                        "token_cost": stats.get("token_cost", 0.0),
                        "active_tasks": stats.get("active_tasks", 0),
                        "completed_tasks": stats.get("completed_tasks", 0),
                        "cost_efficiency": stats.get("cost_efficiency", 0.0),
                        "workload": stats.get("workload", {}),
                        "throughput": stats.get("throughput", []),
                        "prompt_tokens": stats.get("prompt_tokens", 0),
                        "completion_tokens": stats.get("completion_tokens", 0),
                        "total_calls": stats.get("total_calls", 0)
                    }, room=team_name)
                
                # Save stats updates periodically to JSON
                save_squad_stats()
                
                # Calculate and broadcast global metrics for landing tree map
                total_active = sum(s.get("active_tasks", 0) for s in squad_stats.values())
                total_cost = sum(s.get("token_cost", 0.0) for s in squad_stats.values())
                total_divisions = len(squad_stats)
                
                squads_data = {}
                for team, stats in squad_stats.items():
                    squads_data[team] = {
                        "tasks": stats.get("active_tasks", 0) + stats.get("completed_tasks", 0),
                        "active_tasks": stats.get("active_tasks", 0),
                        "cost": f"${stats.get('token_cost', 0.0):.4f}",
                        "raw_cost": stats.get('token_cost', 0.0)
                    }
                
                socketio_server.emit('global_live_analytics_stream', {
                    "total_divisions": total_divisions,
                    "global_active_tasks": total_active,
                    "cumulative_cost": f"${total_cost:.4f}",
                    "raw_cumulative_cost": total_cost,
                    "squads": squads_data
                })
                
            except Exception as e:
                logging.debug(f"[suppressed] Exception as e: {e}")

    threading.Thread(target=broadcast_loop, daemon=True).start()

# Launch the live telemetry broadcaster thread
start_stats_broadcaster()


# ==========================================
#    항목 4: Real-time Agent Chat API
# ==========================================

_execution_results = {}  # In-memory store for execution results

_launchpad_executions = []

_ceo_commands = []  # Legacy in-memory (kept for backward compat)

# ── B1: Initialize Persistent Storage ──
try:
    from chatdev.ceo_persistence import init_db, save_command, list_commands, get_command, \
        update_command_status, delete_command, clear_all_commands, save_job, get_job, list_jobs, \
        add_comment, get_comments, save_attachment, get_attachments, \
        save_schedule, list_schedules, update_schedule, delete_schedule, \
        save_chain, list_chains, get_audit_log, get_analytics, migrate_from_memory
    init_db()
    _ceo_persistence_ok = True
    logging.info("✅ [CEO Persistence] SQLite storage initialized")
except Exception as _pers_err:
    _ceo_persistence_ok = False
    logging.warning(f"[CEO Persistence] Not available: {_pers_err}")

# ── B2-B20: Initialize Integration Modules ──
try:
    from chatdev.ceo_pipeline_integrations import (
        RetryWrapper, WebAgentBridge, APIKeyPool, ParallelDispatcher,
        DivisionMessageBus, RoleAssigner, CostTracker, AutoTestRunner,
        ResultReporter, AutoDeployer, RAGContextInjector, QualityEvaluator,
        ApprovalGate, NotificationSink, SelfEvolver, ScheduleExecutor
    )
    _retry_wrapper = RetryWrapper()
    _web_agent = WebAgentBridge()
    _api_key_pool = APIKeyPool()
    _cost_tracker_ceo = CostTracker()
    _role_assigner = RoleAssigner()
    _auto_tester = AutoTestRunner()
    _result_reporter = ResultReporter()
    _auto_deployer = AutoDeployer()
    _rag_injector = RAGContextInjector()
    _quality_evaluator = QualityEvaluator()
    _approval_gate = ApprovalGate()
    _notification_sink = NotificationSink()
    _self_evolver = SelfEvolver()
    _integrations_ok = True
    logging.info("✅ [CEO Integrations] All B2-B20 modules initialized")
except Exception as _int_err:
    _integrations_ok = False
    logging.warning(f"[CEO Integrations] Not available: {_int_err}")

# ── CEO Command Auto-Dispatcher (connects commands to agent pipeline) ──
try:
    from chatdev.command_dispatcher import CommandDispatcher
    _ceo_dispatcher = CommandDispatcher(socketio=socketio_server, command_store=_ceo_commands)
    logging.info("🚀 [CEO Dispatcher] Auto-dispatch bridge initialized")
    
    # B5: Parallel Dispatcher
    if _integrations_ok:
        _parallel_dispatcher = ParallelDispatcher(_ceo_dispatcher)
        # B6: Message Bus
        _message_bus = DivisionMessageBus(dispatcher=_ceo_dispatcher, socketio=socketio_server)
        # B12: Schedule Executor
        _schedule_executor = ScheduleExecutor(dispatcher=_ceo_dispatcher)
        _schedule_executor.start()
        logging.info("📅 [Schedule Executor] Background scheduler started")
except Exception as _disp_err:
    _ceo_dispatcher = None
    logging.warning(f"[CEO Dispatcher] Not available: {_disp_err}")

# A-6: Bounded dedup cache with max size (prevents unbounded memory growth)
from collections import OrderedDict
_ceo_dedup_cache = OrderedDict()  # {text_hash: timestamp}
_CEO_DEDUP_MAX = 10000  # Maximum entries before eviction

def _analyze_ceo_command(text, target, priority):
    """Analyze CEO command using Ollama LLM first, fallback to rule-based engine."""
    
    # ── Try Ollama (local LLM) first ──
    try:
        import urllib.request
        prompt = f"""당신은 기업 CEO의 AI 비서입니다. 다음 CEO 명령을 분석해주세요.

명령: {text}
대상: {target}
긴급도: {priority}

다음 형식으로 JSON만 출력하세요 (설명 없이):
{{
  "summary": "명령 핵심 요약 (1줄)",
  "action_items": ["실행 항목 1", "실행 항목 2", "실행 항목 3"],
  "suggested_target": "{target}",
  "suggested_priority": "{priority}",
  "risk_level": "low|medium|high",
  "estimated_time": "예상 소요 시간",
  "category": "보고|개발|마케팅|인사|보안|운영|전략|기타",
  "response": "명령 수행 계획 요약 (2-3문장)"
}}"""

        req_data = json.dumps({
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 512}
        }).encode("utf-8")
        
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        # A-5: Configurable timeout via environment variable
        _ceo_timeout = int(os.environ.get("CEO_COMMAND_TIMEOUT", "15"))
        req.timeout = _ceo_timeout
        
        with urllib.request.urlopen(req, timeout=_ceo_timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            response_text = result.get("response", "")
            
            # Extract JSON from response
            import re
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                analysis["engine"] = "ollama"
                analysis["model"] = result.get("model", "llama3.2")
                return analysis
                
    except Exception as e:
        logging.debug(f"👔 Ollama unavailable ({e}), using rule-based engine")
    
    # ── Fallback: Rule-based analysis ──
    return _rule_based_analysis(text, target, priority)


def _rule_based_analysis(text, target, priority):
    """Smart rule-based CEO command analysis when LLM is unavailable."""
    text_lower = text.lower()
    
    # Category detection
    category = "기타"
    category_keywords = {
        "보고": ["보고", "리포트", "report", "상태", "현황", "요약", "정리", "분석"],
        "개발": ["개발", "코딩", "구현", "배포", "릴리즈", "버그", "테스트", "기능"],
        "마케팅": ["마케팅", "캠페인", "홍보", "광고", "소셜", "브랜드", "콘텐츠"],
        "인사": ["인사", "채용", "교육", "평가", "팀빌딩", "온보딩", "인력"],
        "보안": ["보안", "취약점", "점검", "감사", "권한", "인증", "방화벽"],
        "운영": ["운영", "프로세스", "효율", "비용", "절감", "자동화", "워크플로"],
        "전략": ["전략", "로드맵", "비전", "목표", "계획", "분기", "연간"]
    }
    for cat, keywords in category_keywords.items():
        if any(kw in text_lower for kw in keywords):
            category = cat
            break
    
    # Priority upgrade detection
    suggested_priority = priority
    urgent_words = ["긴급", "즉시", "비상", "위기", "장애", "다운", "지금", "바로", "ASAP", "urgent"]
    important_words = ["중요", "우선", "핵심", "critical", "반드시", "필수"]
    if any(w in text_lower for w in urgent_words):
        suggested_priority = "urgent"
    elif any(w in text_lower for w in important_words):
        suggested_priority = "important"
    
    # Target suggestion
    suggested_target = target
    team_keywords = {
        "Squad_A": ["A팀", "squad a", "스쿼드A", "개발팀"],
        "Squad_B": ["B팀", "squad b", "스쿼드B", "마케팅팀"],
        "Squad_C": ["C팀", "squad c", "스쿼드C", "디자인팀"],
    }
    for team, keywords in team_keywords.items():
        if any(kw.lower() in text_lower for kw in keywords):
            suggested_target = team
            break
    
    # Risk assessment
    risk_level = "low"
    high_risk_words = ["삭제", "리셋", "초기화", "해고", "폐쇄", "중단", "철수"]
    medium_risk_words = ["변경", "수정", "재구성", "이전", "마이그레이션"]
    if any(w in text_lower for w in high_risk_words):
        risk_level = "high"
    elif any(w in text_lower for w in medium_risk_words):
        risk_level = "medium"
    
    # Time estimation
    if any(w in text_lower for w in ["즉시", "바로", "지금"]):
        estimated_time = "즉시 (30분 이내)"
    elif any(w in text_lower for w in ["오늘", "today"]):
        estimated_time = "오늘 이내"
    elif any(w in text_lower for w in ["이번 주", "금주"]):
        estimated_time = "이번 주 이내"
    else:
        estimated_time = "1~3일"
    
    # Generate action items
    action_items = []
    if "보고" in text_lower or "분석" in text_lower:
        action_items.extend(["데이터 수집 및 현황 파악", "분석 리포트 작성", "CEO에게 보고 발송"])
    elif "개발" in text_lower or "구현" in text_lower:
        action_items.extend(["요구사항 분석", "개발 착수 및 테스트", "결과 리뷰 및 배포"])
    elif "점검" in text_lower or "감사" in text_lower:
        action_items.extend(["점검 대상 범위 확정", "점검 실행 및 결과 기록", "개선 사항 보고"])
    else:
        action_items.extend(["명령 내용 확인 및 계획 수립", "담당자 배정 및 작업 착수", "완료 후 결과 보고"])
    
    # Build response text
    target_label = "전체 Division" if suggested_target == "all" else suggested_target
    response = f"{category} 관련 명령을 {target_label}에 전달합니다. "
    response += f"예상 소요 시간은 {estimated_time}이며, "
    response += f"위험도는 {'높음 — 신중한 검토 필요' if risk_level == 'high' else '보통' if risk_level == 'medium' else '낮음'}입니다."
    
    return {
        "summary": text[:60] + ("..." if len(text) > 60 else ""),
        "action_items": action_items,
        "suggested_target": suggested_target,
        "suggested_priority": suggested_priority,
        "risk_level": risk_level,
        "estimated_time": estimated_time,
        "category": category,
        "response": response,
        "engine": "rule-based"
    }


_ceo_scheduled = []  # Scheduled/recurring commands
_ceo_chains = []     # Command chains

_CEO_TEMPLATES = [
    {"id": "report-weekly", "category": "보고", "icon": "📊", "name": "주간 보고 요청",
     "text": "{division}에서 이번 주 성과 보고서를 작성하세요. KPI 달성률, 주요 이슈, 다음 주 계획을 포함하세요.",
     "priority": "normal", "est_time": "2~4시간"},
    {"id": "report-status", "category": "보고", "icon": "📋", "name": "현황 보고 요청",
     "text": "전체 Division의 현재 프로젝트 진행 상황을 요약 보고하세요.",
     "priority": "important", "est_time": "1~2시간"},
    {"id": "dev-feature", "category": "개발", "icon": "💻", "name": "신규 기능 개발",
     "text": "{description} 기능을 개발하세요. 기술 스펙, 일정, 필요 리소스를 포함한 계획서를 먼저 제출하세요.",
     "priority": "normal", "est_time": "1~2주"},
    {"id": "dev-bugfix", "category": "개발", "icon": "🐛", "name": "버그 수정 긴급",
     "text": "{description} 버그를 즉시 수정하세요. 원인 분석과 재발 방지 대책도 보고하세요.",
     "priority": "urgent", "est_time": "2~8시간"},
    {"id": "marketing-campaign", "category": "마케팅", "icon": "📣", "name": "캠페인 기획",
     "text": "{description} 마케팅 캠페인을 기획하세요. 타겟 고객, 채널 전략, 예산 계획을 포함하세요.",
     "priority": "important", "est_time": "3~5일"},
    {"id": "hr-recruit", "category": "인사", "icon": "👥", "name": "채용 요청",
     "text": "{position} 포지션 채용을 시작하세요. JD 작성, 채용 채널 선정, 면접 프로세스를 수립하세요.",
     "priority": "normal", "est_time": "1~4주"},
    {"id": "security-audit", "category": "보안", "icon": "🔒", "name": "보안 감사",
     "text": "전체 시스템 보안 감사를 실시하세요. 취약점 스캔, 접근 권한 검토, 컴플라이언스 체크를 포함하세요.",
     "priority": "urgent", "est_time": "1~3일"},
    {"id": "ops-deploy", "category": "운영", "icon": "🚀", "name": "배포 요청",
     "text": "{version} 버전을 프로덕션 환경에 배포하세요. 롤백 계획과 모니터링 체크리스트를 준비하세요.",
     "priority": "urgent", "est_time": "2~4시간"},
    {"id": "strategy-research", "category": "전략", "icon": "🔍", "name": "시장 조사",
     "text": "{topic}에 대한 시장 조사를 실시하세요. 경쟁사 분석, 시장 규모, 기회 영역을 포함하세요.",
     "priority": "normal", "est_time": "1~2주"},
    {"id": "strategy-roadmap", "category": "전략", "icon": "🗺️", "name": "로드맵 수립",
     "text": "다음 분기 {division} 로드맵을 수립하세요. 목표, 마일스톤, 리소스 배분을 포함하세요.",
     "priority": "important", "est_time": "3~5일"}
]


try:
    from visualizer.backend.ceo_report_engine import (
        generate_report as _generate_report,
        get_report as _get_report,
        list_reports as _list_reports
    )
    _report_engine_loaded = True
    logging.info("[CEO] Report Engine loaded")
except ImportError:
    try:
        from backend.ceo_report_engine import (
            generate_report as _generate_report,
            get_report as _get_report,
            list_reports as _list_reports
        )
        _report_engine_loaded = True
        logging.info("[CEO] Report Engine loaded (relative)")
    except ImportError:
        _report_engine_loaded = False
        logging.info("[CEO] Report Engine not available")


try:
    from chatdev.cross_squad_bus import CrossSquadMessageBus
    _cross_squad_bus = CrossSquadMessageBus()
    logging.info("✅ [B6] CrossSquadBus loaded")
except Exception:
    _cross_squad_bus = None

try:
    from chatdev.data_center import CentralDataCenter
    _data_center = CentralDataCenter()
    logging.info("✅ [B7] DataCenter loaded")
except Exception:
    _data_center = None

try:
    from chatdev.eval_quality import get_code, get_completeness, get_executability, get_consistency
    _eval_quality_loaded = True
    logging.info("✅ [B8] EvalQuality loaded")
except Exception:
    _eval_quality_loaded = False

try:
    from chatdev.executive_board import CEOOrchestrator
    _ceo_orchestrator = CEOOrchestrator()
    logging.info("✅ [B9] ExecutiveBoard loaded")
except Exception:
    _ceo_orchestrator = None

try:
    from chatdev.knowledge_connector import KnowledgeConnector
    _knowledge_loaded = True
    logging.info("✅ [B10] KnowledgeConnector loaded")
except Exception:
    _knowledge_loaded = False

try:
    from chatdev.omnichannel_sink import OmniChannelSink
    _omni_sink_loaded = True
    logging.info("✅ [B11] OmniChannelSink loaded")
except Exception:
    _omni_sink_loaded = False

try:
    from chatdev.parallel_pipeline import ParallelPipelineManager, ProjectSpec
    _parallel_mgr = ParallelPipelineManager()
    logging.info("✅ [B12] ParallelPipeline loaded")
except Exception:
    _parallel_mgr = None

try:
    from chatdev.plugin_system import PluginRegistry
    _plugin_registry_loaded = True
    logging.info("✅ [B13] PluginSystem loaded")
except Exception:
    try:
        from chatdev.plugin_system import PhasePlugin, ToolPlugin
        _plugin_registry_loaded = True
    except Exception:
        _plugin_registry_loaded = False

try:
    from chatdev.session_timeout import SessionTimeoutGuard
    _session_timeout_loaded = True
    logging.info("✅ [B14] SessionTimeout loaded")
except Exception:
    _session_timeout_loaded = False

try:
    from chatdev.tool_registry import ToolRegistry
    _tool_registry = ToolRegistry
    logging.info("✅ [B15] ToolRegistry loaded")
except Exception:
    _tool_registry = None

try:
    from chatdev.vector_db import VectorDBLayer
    _vector_db = VectorDBLayer()
    logging.info("✅ [B16] VectorDB loaded")
except Exception:
    _vector_db = None

try:
    from chatdev.vision_healing import VisionHealingLoop
    _vision_healer = VisionHealingLoop()
    logging.info("✅ [B17] VisionHealing loaded")
except Exception:
    _vision_healer = None

try:
    from chatdev.web_operator import WebOperator
    _web_operator_loaded = True
    logging.info("✅ [B18] WebOperator loaded")
except Exception:
    _web_operator_loaded = False

try:
    from chatdev.approval_system import ApprovalSystem
    _approval_sys = ApprovalSystem()
    logging.info("✅ [B19] ApprovalSystem loaded")
except Exception:
    _approval_sys = None

try:
    from chatdev.self_evolving_loop import SelfEvolvingLoop
    _self_evolving = SelfEvolvingLoop()
    logging.info("✅ [B20] SelfEvolvingLoop loaded")
except Exception:
    _self_evolving = None

try:
    from chatdev.context_manager import ContextManager
    _root_dir_ctx = ROOT_DIR  # #4
    _context_mgr = ContextManager(os.path.join(_root_dir_ctx, "WareHouse"))
    logging.info("✅ [B21] ContextManager loaded")
except Exception:
    _context_mgr = None

try:
    from chatdev.ai_router import AIRouter
    _ai_router = AIRouter()
    logging.info("✅ [B22] AIRouter loaded")
except Exception:
    _ai_router = None

try:
    from visualizer.backend.auth import verify_api_key, verify_token
    _auth_module_loaded = True
except Exception:
    _auth_module_loaded = False

@app.before_request
def ceo_auth_check():
    """C23: Optional auth check for CEO mutation endpoints."""
    # Only enforce if AUTH_REQUIRED env is set
    if not os.environ.get("CEO_AUTH_REQUIRED"):
        return None
    if not _auth_module_loaded:
        return None
    # Only check POST/PUT/DELETE on CEO endpoints
    if request.path.startswith("/api/ceo/") and request.method in ("POST", "PUT", "DELETE"):
        auth_header = request.headers.get("Authorization", "")
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            result = verify_api_key(api_key)
            if not result.get("valid"):
                return jsonify({"status": "error", "message": "Invalid API key"}), 401
        elif auth_header.startswith("Bearer "):
            result = verify_token(auth_header[7:])
            if not result.get("valid"):
                return jsonify({"status": "error", "message": "Invalid token"}), 401
        else:
            return jsonify({"status": "error", "message": "Authentication required"}), 401
    return None


# ═══════════════════════════════════════════════════════
#  🟢 C24: Cache Layer for Analytics
# ═══════════════════════════════════════════════════════
_analytics_cache = {"data": None, "ts": 0, "ttl": 60}

_ceo_rate_limiter = {"window": [], "max_per_minute": 30}

@app.before_request
def ceo_rate_limit_check():
    """C25: Rate limit CEO command submissions."""
    if request.path == "/api/ceo/command" and request.method == "POST":
        import time as _time
        now = _time.time()
        _ceo_rate_limiter["window"] = [t for t in _ceo_rate_limiter["window"] if now - t < 60]
        if len(_ceo_rate_limiter["window"]) >= _ceo_rate_limiter["max_per_minute"]:
            return jsonify({"status": "error", "message": "Rate limit exceeded (30/min)"}), 429
        _ceo_rate_limiter["window"].append(now)
    return None


# ═══════════════════════════════════════════════════════
#  🟢 C26: Webhook Queue — Pipeline Event Dispatch
# ═══════════════════════════════════════════════════════
try:
    from visualizer.backend.webhook_queue import WebhookProcessor
    _webhook_queue = WebhookProcessor()
    logging.info("✅ [C26] WebhookQueue loaded")
except Exception:
    _webhook_queue = None

try:
    from visualizer.backend.workflow_recovery import WorkflowRecoveryEngine
    _workflow_recovery = WorkflowRecoveryEngine()
    logging.info("✅ [C27] WorkflowRecovery loaded")
except Exception:
    _workflow_recovery = None

try:
    from chatdev.hf_model_manager import (
        search_models as hf_search, get_model_info as hf_info,
        download_model as hf_download, list_installed as hf_installed,
        delete_model as hf_delete, activate_model as hf_activate,
        get_download_progress as hf_progress, get_ollama_models,
    )
    _hf_manager_ok = True
    logging.info("✅ [HF Model Manager] Loaded")
except Exception as _hf_err:
    _hf_manager_ok = False
    logging.warning(f"[HF Model Manager] Not available: {_hf_err}")


def _sync_knowledge_internal(team_name="Squad_A"):
    # Get injected files
    injected = squad_injected_knowledge.get(team_name, [])
    if not injected:
        return {"synced": 0, "books": [], "message": "주입된 지식이 없습니다."}

    synced = []
    book_node_ids = []

    for fname in injected:
        # Derive a clean title from filename
        title = fname
        for ext in ['.pdf', '.txt', '.md', '.docx', '.epub']:
            if title.lower().endswith(ext):
                title = title[:-len(ext)]
                break

        # Auto-detect tags from filename patterns
        tags = ["knowledge", "synced"]
        if "(OCR)" in fname:
            tags.append("OCR")
        ext = os.path.splitext(fname)[1].lower()
        if ext == '.pdf':
            tags.append("PDF")
        elif ext == '.md':
            tags.append("마크다운")

        # Get file size for content description
        knowledge_dir = os.path.join(ROOT_DIR, "CompanyConfig", "Knowledge")
        fpath = os.path.join(knowledge_dir, fname)
        fsize = ""
        if os.path.exists(fpath):
            size_mb = os.path.getsize(fpath) / (1024 * 1024)
            fsize = f" | 파일 크기: {size_mb:.1f}MB"

        content = f"Knowledge(RAG) 시스템에서 동기화된 학습 자료.{fsize}\n원본 파일: {fname}"

        node = add_knowledge(
            title=title,
            content=content,
            node_type="book",
            tags=tags,
            source=f"knowledge-sync:{team_name}",
            importance=3,
        )
        if node and "error" not in node:
            # If merged into existing node, force update type to 'book'
            if node.get("merged") and node.get("node_type") != "book":
                update_knowledge(node["id"], node_type="book")
                node["node_type"] = "book"
            synced.append(node)
            book_node_ids.append(node.get("id"))

    # Link all books together with 'related' edges
    for i in range(len(book_node_ids)):
        for j in range(i + 1, min(i + 3, len(book_node_ids))):
            if book_node_ids[i] and book_node_ids[j]:
                link_knowledge(book_node_ids[i], book_node_ids[j], "related", 0.5)

    return {
        "synced": len(synced),
        "books": synced,
        "message": f"📚 {len(synced)}권의 책이 뇌 그래프에 동기화되었습니다."
    }


try:
    from chatdev.book_pipeline import BookPipeline
    _book_pipeline = BookPipeline()
    _book_ok = True
    logging.info("✅ [Book Pipeline] Loaded")
except Exception as _book_err:
    _book_ok = False
    _book_pipeline = None
    logging.warning(f"[Book Pipeline] Not available: {_book_err}")


try:
    from chatdev.brain_knowledge import (
        add_knowledge, get_knowledge, update_knowledge, delete_knowledge,
        link_knowledge, unlink_knowledge, get_brain_graph,
        search_knowledge as brain_search, get_knowledge_stats,
        get_knowledge_tree, auto_extract_knowledge,
        export_obsidian, execute_console_command,
        find_duplicate_nodes, merge_nodes,             # #5: Duplicate detection
        export_knowledge_json, import_knowledge_json,  # #30: Export/Import
        NODE_TYPES as BRAIN_NODE_TYPES, EDGE_TYPES as BRAIN_EDGE_TYPES,
    )
    _brain_ok = True
    logging.info("✅ [Brain Knowledge] Loaded")
except Exception as _brain_err:
    _brain_ok = False
    logging.warning(f"[Brain Knowledge] Not available: {_brain_err}")


# NOTE: /api/brain/graph is now registered as api_brain_graph_cached with caching (#8)


_api_cache = {}
_CACHE_TTL = 30  # seconds

def _cached_response(key, ttl=None):
    """Get cached response if still valid."""
    if key in _api_cache:
        entry = _api_cache[key]
        if time.time() - entry["ts"] < (ttl or _CACHE_TTL):
            return entry["data"]
    return None

def _set_cache(key, data, ttl=None):
    """Cache a response."""
    _api_cache[key] = {"data": data, "ts": time.time()}

def _api_response(data=None, message="", status="success", code=200, meta=None):
    """#23: Standard API response format."""
    resp = {"status": status, "message": message}
    if data is not None:
        resp["data"] = data
    if meta:
        resp["meta"] = meta
    return jsonify(resp), code


# ═══════════════════════════════════════════
#  #25: Centralized Configuration API
# ═══════════════════════════════════════════
def _scheduled_cleanup():
    """Run cleanup tasks periodically (#23, #25)."""
    while True:
        time.sleep(3600)  # Every hour
        try:
            if _backend_utils_ok:
                cleanup_expired_uploads()
        except Exception as e:
            logging.error(f"[Scheduler] Cleanup error: {e}")

_cleanup_thread = threading.Thread(target=_scheduled_cleanup, daemon=True)
_cleanup_thread.start()


# ═══════════════════════════════════════════════════════
#  #7: System Stats Background Cache (10-second TTL)
# ═══════════════════════════════════════════════════════
_system_stats_cache = {"data": None, "updated_at": 0}
_system_stats_lock = threading.Lock()
SYSTEM_STATS_TTL = 10  # seconds

def _collect_system_stats_background():
    """Background thread to collect system stats every 10 seconds."""
    import subprocess
    import platform

    while True:
        try:
            stats = {
                "cpu": {"percent": 0, "cores": 0, "load_avg": [0, 0, 0]},
                "memory": {"total_gb": 0, "used_gb": 0, "percent": 0},
                "disk": {"total_gb": 0, "used_gb": 0, "percent": 0},
                "processes": {"total": 0, "python": 0},
                "platform": platform.system(),
                "timestamp": datetime.now().isoformat(),
            }
            
            # CPU
            try:
                import psutil
                stats["cpu"]["percent"] = psutil.cpu_percent(interval=0.5)
                stats["cpu"]["cores"] = psutil.cpu_count()
                stats["cpu"]["load_avg"] = [round(x, 2) for x in psutil.getloadavg()]
            except ImportError:
                cores = int(subprocess.check_output(["sysctl", "-n", "hw.ncpu"]).strip())
                stats["cpu"]["cores"] = cores
                load = os.getloadavg()
                stats["cpu"]["load_avg"] = [round(x, 2) for x in load]
                # Use 'ps' to get actual CPU usage (sum of all process CPU / cores)
                try:
                    ps_out = subprocess.check_output(
                        ["ps", "-A", "-o", "%cpu"], timeout=3
                    ).decode().strip().split('\n')[1:]  # skip header
                    total_cpu = sum(float(x.strip()) for x in ps_out if x.strip())
                    stats["cpu"]["percent"] = round(min(total_cpu / cores, 100), 1)
                except Exception:
                    # Final fallback: scale load_avg but don't cap at 100 blindly
                    # Use 1-min load relative to cores, scale non-linearly
                    ratio = load[0] / cores
                    if ratio <= 1.0:
                        pct = ratio * 70  # 70% at full load per core
                    else:
                        pct = 70 + min((ratio - 1.0) * 15, 30)  # 70-100% for overload
                    stats["cpu"]["percent"] = round(pct, 1)

            # Memory
            try:
                import psutil
                mem = psutil.virtual_memory()
                stats["memory"]["total_gb"] = round(mem.total / (1024**3), 1)
                stats["memory"]["used_gb"] = round(mem.used / (1024**3), 1)
                stats["memory"]["percent"] = mem.percent
            except ImportError:
                mem_bytes = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip())
                stats["memory"]["total_gb"] = round(mem_bytes / (1024**3), 1)

            # Disk
            try:
                import psutil
                disk = psutil.disk_usage("/")
                stats["disk"]["total_gb"] = round(disk.total / (1024**3), 1)
                stats["disk"]["used_gb"] = round(disk.used / (1024**3), 1)
                stats["disk"]["percent"] = disk.percent
            except ImportError:
                df_output = subprocess.check_output(["df", "-g", "/"]).decode().split("\n")
                if len(df_output) > 1:
                    parts = df_output[1].split()
                    if len(parts) >= 5:
                        stats["disk"]["total_gb"] = int(parts[1])
                        stats["disk"]["used_gb"] = int(parts[2])
                        stats["disk"]["percent"] = int(parts[4].replace("%", ""))

            # Processes
            try:
                import psutil
                stats["processes"]["total"] = len(psutil.pids())
            except ImportError:
                ps_output = subprocess.check_output(["ps", "aux"]).decode()
                stats["processes"]["total"] = max(len(ps_output.strip().split("\n")) - 1, 0)

            with _system_stats_lock:
                _system_stats_cache["data"] = stats
                _system_stats_cache["updated_at"] = time.time()

            # #12: Push stats via SocketIO instead of requiring frontend polling
            try:
                socketio_server.emit('system_stats_update', stats, namespace='/')
            except Exception:
                pass  # SocketIO may not be ready during startup

        except Exception as e:
            logging.debug(f"[SystemStatsCollector] Error: {e}")

        time.sleep(SYSTEM_STATS_TTL)

_stats_collector_thread = threading.Thread(target=_collect_system_stats_background, daemon=True)
_stats_collector_thread.start()


# ═══════════════════════════════════════════════════════
#  #25: Unified Health Check Endpoint
# ═══════════════════════════════════════════════════════

def _graceful_shutdown(signum, frame):
    """Handle SIGTERM/SIGINT for clean shutdown."""
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"\n{'='*60}")
    logging.info(f"🛑 Received {sig_name} — Initiating graceful shutdown...")
    logging.info(f"{'='*60}")
    
    # 1. Save current state
    try:
        save_squad_stats()
        logging.info("  ✅ Squad stats saved")
    except Exception as e:
        logging.error(f"  ❌ Failed to save stats: {e}")
    
    # 2. Close DB connections
    try:
        if _backend_utils_ok:
            import sqlite3
            # WAL checkpoint for data integrity
            conn = get_db_connection()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            logging.info("  ✅ Database WAL checkpoint completed")
    except Exception as e:
        logging.error(f"  ❌ DB checkpoint error: {e}")
    
    logging.info("  👋 Shutdown complete. Goodbye!")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)


# ═══════════════════════════════════════════════════════
#  #30: Health Check Endpoint
# ═══════════════════════════════════════════════════════

_LLM_PATHS = {
    "/api/workflow/execute", "/api/workflow/execute_bg",
    "/api/workflow/generate", "/api/workflow/alignment",
    "/api/workflow/align/questions", "/api/workflow/align/synthesize",
}

# Read-only polling paths that the UI calls automatically (every 5-15s).
# These must NOT count against rate limits or normal browsing triggers 429.
_POLLING_EXEMPT_PATHS = {
    "/api/system/stats",
    "/api/workflow_engine/notifications",
    "/api/workflow_engine/stats/summary",
    "/api/workflow_engine/cron/status",
    "/api/execution/history",
    "/api/playbooks",
    "/api/teams",
}

@app.before_request
def rate_limit_check():
    """#24: Rate limiting for API endpoints."""
    path = request.path
    
    # Skip non-API paths
    if not path.startswith("/api/"):
        return None
    
    # Exempt read-only polling endpoints from rate limiting
    if path in _POLLING_EXEMPT_PATHS:
        return None
    
    client_ip = request.remote_addr or "unknown"
    
    # Strict limit for LLM-consuming endpoints
    if path in _LLM_PATHS:
        if not llm_rate_limiter.allow(client_ip):
            return jsonify({
                "status": "error",
                "message": "Rate limit exceeded. LLM endpoints: max 10 requests/minute.",
                "retry_after_seconds": 60
            }), 429
    
    # General API rate limit (raised from 30 to 300 for interactive UI usage)
    if not workflow_rate_limiter.allow(client_ip):
        return jsonify({
            "status": "error",
            "message": "Rate limit exceeded. Max 300 requests/minute.",
            "retry_after_seconds": 30
        }), 429
    
    return None


# ═══════════════════════════════════════════════════════
#  #25: API Version Prefix (v1 aliases)
# ═══════════════════════════════════════════════════════

# Register versioned aliases for key workflow endpoints
_V1_ALIASES = [
    ("/api/v1/workflow/execute", "/api/workflow/execute"),
    ("/api/v1/workflow/execute_bg", "/api/workflow/execute_bg"),
    ("/api/v1/workflow/generate", "/api/workflow/generate"),
    ("/api/v1/workflow/alignment", "/api/workflow/alignment"),
    ("/api/v1/workflow/tasks", "/api/workflow/tasks"),
    ("/api/v1/health", "/api/health"),
    ("/api/v1/pipeline/status", "/api/pipeline/status"),
    ("/api/v1/pipeline/chains", "/api/pipeline/chains"),
]

for v1_path, original_path in _V1_ALIASES:
    try:
        # Create redirect rule for v1 prefix
        app.add_url_rule(
            v1_path,
            endpoint=f"v1_alias_{v1_path.replace('/', '_')}",
            redirect_to=original_path,
            methods=["GET", "POST", "PUT", "DELETE"]
        )
    except Exception:
        pass  # Silently skip if rule conflicts


# ═══════════════════════════════════════════════════════
#  #23: Pagination Helper
# ═══════════════════════════════════════════════════════

def paginate_list(items, page=1, limit=20):
    """#23: Apply pagination to a list of items.
    
    Returns:
        dict with 'items', 'page', 'limit', 'total', 'total_pages'
    """
    total = len(items)
    total_pages = max(1, (total + limit - 1) // limit)
    page = max(1, min(page, total_pages))
    start = (page - 1) * limit
    end = start + limit
    
    return {
        "items": items[start:end],
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages
    }


def paginate_sql(conn, base_sql, params=None, page=1, limit=20, count_sql=None):
    """D-6: Cursor-based SQL pagination — uses LIMIT/OFFSET at the DB level.
    
    More efficient than paginate_list() for database queries since it avoids
    loading all rows into memory before slicing.
    
    Args:
        conn: SQLite connection
        base_sql: Base SELECT query (without LIMIT/OFFSET)
        params: Query parameters tuple/list
        page: Page number (1-indexed)
        limit: Items per page
        count_sql: Optional custom count query (auto-generated if None)
    
    Returns:
        dict with 'items', 'page', 'limit', 'total', 'total_pages'
    """
    params = params or []
    page = max(1, page)
    offset = (page - 1) * limit
    
    # Count total
    if count_sql is None:
        count_sql = f"SELECT COUNT(*) FROM ({base_sql})"
    total = conn.execute(count_sql, params).fetchone()[0]
    total_pages = max(1, (total + limit - 1) // limit)
    
    # Fetch page
    paginated_sql = f"{base_sql} LIMIT ? OFFSET ?"
    rows = conn.execute(paginated_sql, list(params) + [limit, offset]).fetchall()
    
    return {
        "items": [dict(r) for r in rows] if rows else [],
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages
    }


# ═══════════════════════════════════════════════════════
#  Server Entry Point (must be at end of file)
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ChatDev Enterprise Dashboard')
    parser.add_argument('--port', type=int, default=8000, help="port")
    parser.add_argument('--production', action='store_true', help="Enable production mode with hardened security")
    args = parser.parse_args()
    server_port = args.port  # #30: Simple integer assignment
    
    if args.production:
        # 🔒 Production Security Hardening
        app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(32).hex())
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        app.config['SESSION_COOKIE_SECURE'] = False  # Set True when behind HTTPS proxy
        app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session timeout
        
        logging.info(f"\n{'='*72}")
        logging.info(f"🔒 PRODUCTION MODE — Security Hardening Active")
        logging.info(f"{'='*72}")
        logging.info(f"  ✅ Session cookies: HttpOnly + SameSite=Lax")
        logging.info(f"  ✅ Secret key: {'ENV' if os.environ.get('FLASK_SECRET_KEY') else 'AUTO-GENERATED'}")
        logging.info(f"  ✅ Debug mode: DISABLED")
        logging.info(f"  ✅ Saved workflows dir: {os.path.join(VISUALIZER_DIR, 'saved_workflows')}")
        server_host = os.environ.get('CHATDEV_HOST', '0.0.0.0')
        logging.info(f"\n  🚀 Starting on {server_host}:{server_port}...")
        logging.info(f"  🔗 http://{server_host}:{server_port}/")
        logging.info(f"\n  📦 For multi-worker production deployment with gunicorn:")
        logging.info(f"     gunicorn -k eventlet -w 1 -b {server_host}:{server_port} visualizer.app:app")
        logging.info(f"{'='*72}\n")
        
        socketio_server.run(app, host=server_host, debug=False, port=server_port, allow_unsafe_werkzeug=False)
    else:
        # Development mode
        # #18: Explicit unsafe werkzeug warning
        logging.warning("⚠️ [Security] Development mode: allow_unsafe_werkzeug=True — DO NOT use in production!")
        logging.info(f"\n{'='*72}")
        logging.info(f"🚀 ChatDev Enterprise Dashboard — DEV MODE — port {server_port}")
        logging.info(f"🔗 http://127.0.0.1:{server_port}/")
        if _has_google_creds:
            logging.info(f"🔐 Google Drive: ✅ OAuth 2.0 LIVE (credentials loaded from .env)")
        else:
            logging.info(f"🏖️ Google Drive: Sandbox Mode (set .env for real OAuth)")
            logging.info(f"   → cp .env.template .env && edit with your Google credentials")
        logging.info(f"{'='*72}\n")
        server_host = os.environ.get('CHATDEV_HOST', '0.0.0.0')  # 개선-27
        socketio_server.run(app, host=server_host, debug=False, port=server_port, allow_unsafe_werkzeug=True)
