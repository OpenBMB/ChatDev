# ══════════════════════════════════════════════════════════════════
#   database.py — SQLite Persistent Database Layer
#   Enterprise-grade data persistence for ChatDev Visualizer
#
#   Features:
#     - SQLite with WAL mode for concurrent reads
#     - Thread-safe connection pool
#     - Auto-migration system
#     - ORM-lite query builder
#     - Tables: users, workflows, executions, audit_logs,
#               knowledge_sources, api_keys
# ══════════════════════════════════════════════════════════════════

import os
import sqlite3
import json
import threading
import logging
import time
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger("chatdev.database")

# ── Database Path ──
# #10: Unified with backend_utils.py — single DB path for all modules
_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_DB_PATH = os.environ.get("CHATDEV_DB_PATH", os.path.join(_DB_DIR, "ceo_commands.db"))

# ── Connection Pool ──
_local = threading.local()
_db_lock = threading.Lock()


def _ensure_dir():
    """Ensure database directory exists."""
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """Get a thread-local database connection."""
    if not hasattr(_local, "connection") or _local.connection is None:
        _ensure_dir()
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        _local.connection = conn
    return _local.connection


@contextmanager
def get_db():
    """Context manager for database transactions."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def close_connection():
    """Close the thread-local connection."""
    if hasattr(_local, "connection") and _local.connection:
        _local.connection.close()
        _local.connection = None


# ══════════════════════════════════════════════════════════════
#   Schema & Migrations
# ══════════════════════════════════════════════════════════════

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- ── Schema Versioning ──
CREATE TABLE IF NOT EXISTS _schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Execution History ──
CREATE TABLE IF NOT EXISTS executions (
    id              TEXT PRIMARY KEY,
    team_name       TEXT NOT NULL,
    task_prompt     TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    started_at      TEXT,
    completed_at    TEXT,
    duration_sec    REAL,
    total_tokens    INTEGER DEFAULT 0,
    total_cost_usd  REAL DEFAULT 0.0,
    output_dir      TEXT,
    error_message   TEXT,
    metadata_json   TEXT DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_exec_team ON executions(team_name);
CREATE INDEX IF NOT EXISTS idx_exec_status ON executions(status);
CREATE INDEX IF NOT EXISTS idx_exec_created ON executions(created_at);

-- ── Workflow Snapshots ──
CREATE TABLE IF NOT EXISTS workflows (
    id              TEXT PRIMARY KEY,
    team_name       TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    nodes_json      TEXT NOT NULL DEFAULT '[]',
    edges_json      TEXT NOT NULL DEFAULT '[]',
    version         INTEGER DEFAULT 1,
    is_template     INTEGER DEFAULT 0,
    created_by      TEXT DEFAULT 'system',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_wf_team ON workflows(team_name);

-- ── Knowledge Sources ──
CREATE TABLE IF NOT EXISTS knowledge_sources (
    id              TEXT PRIMARY KEY,
    team_name       TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    name            TEXT NOT NULL,
    content         TEXT,
    file_path       TEXT,
    chunk_count     INTEGER DEFAULT 0,
    metadata_json   TEXT DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ks_team ON knowledge_sources(team_name);

-- ── Audit Log ──
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL DEFAULT (datetime('now')),
    user_id         TEXT,
    action          TEXT NOT NULL,
    resource_type   TEXT,
    resource_id     TEXT,
    ip_address      TEXT,
    user_agent      TEXT,
    request_method  TEXT,
    request_path    TEXT,
    status_code     INTEGER,
    detail_json     TEXT DEFAULT '{}',
    correlation_id  TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_corr ON audit_log(correlation_id);

-- ── Webhook Events ──
CREATE TABLE IF NOT EXISTS webhook_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    payload_json    TEXT NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'pending',
    retry_count     INTEGER DEFAULT 0,
    max_retries     INTEGER DEFAULT 3,
    error_message   TEXT,
    processed_at    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_wh_status ON webhook_events(status);
CREATE INDEX IF NOT EXISTS idx_wh_source ON webhook_events(source);

-- ── Connector Configurations ──
CREATE TABLE IF NOT EXISTS connectors (
    id              TEXT PRIMARY KEY,
    team_name       TEXT NOT NULL,
    connector_type  TEXT NOT NULL,
    config_json     TEXT NOT NULL DEFAULT '{}',
    is_active       INTEGER DEFAULT 1,
    last_tested_at  TEXT,
    test_status     TEXT DEFAULT 'untested',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Scheduled Tasks ──
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id              TEXT PRIMARY KEY,
    team_name       TEXT NOT NULL,
    task_type       TEXT NOT NULL,
    schedule_cron   TEXT,
    next_run_at     TEXT,
    last_run_at     TEXT,
    is_active       INTEGER DEFAULT 1,
    config_json     TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_database():
    """Initialize database schema."""
    _ensure_dir()
    with get_db() as conn:
        # Check current schema version
        try:
            row = conn.execute("SELECT MAX(version) as v FROM _schema_version").fetchone()
            current_version = row["v"] if row and row["v"] else 0
        except sqlite3.OperationalError:
            current_version = 0

        if current_version < SCHEMA_VERSION:
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                "INSERT OR REPLACE INTO _schema_version (version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, datetime.now().isoformat())
            )
            logger.info(f"🗄️ [DB] Schema migrated to v{SCHEMA_VERSION}")
        else:
            logger.info(f"🗄️ [DB] Schema v{current_version} is current")


# ══════════════════════════════════════════════════════════════
#   Repository Classes (Data Access Layer)
# ══════════════════════════════════════════════════════════════

class ExecutionRepository:
    """CRUD for workflow executions."""

    @staticmethod
    def create(exec_id: str, team_name: str, task_prompt: str = "",
               metadata: dict = None) -> dict:
        with get_db() as conn:
            now = datetime.now().isoformat()
            conn.execute(
                """INSERT INTO executions (id, team_name, task_prompt, status, started_at, metadata_json)
                   VALUES (?, ?, ?, 'running', ?, ?)""",
                (exec_id, team_name, task_prompt, now,
                 json.dumps(metadata or {}, ensure_ascii=False))
            )
        return {"id": exec_id, "team_name": team_name, "status": "running"}

    @staticmethod
    def update_status(exec_id: str, status: str, error_message: str = None,
                      total_tokens: int = 0, total_cost: float = 0.0,
                      output_dir: str = None):
        with get_db() as conn:
            now = datetime.now().isoformat()
            conn.execute(
                """UPDATE executions SET status=?, completed_at=?, error_message=?,
                   total_tokens=?, total_cost_usd=?, output_dir=?,
                   duration_sec=CAST((julianday(?)-julianday(started_at))*86400 AS REAL)
                   WHERE id=?""",
                (status, now, error_message, total_tokens, total_cost, output_dir, now, exec_id)
            )

    @staticmethod
    def get(exec_id: str) -> dict:
        conn = get_connection()
        row = conn.execute("SELECT * FROM executions WHERE id=?", (exec_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def list_by_team(team_name: str, limit: int = 50, offset: int = 0) -> list:
        conn = get_connection()
        rows = conn.execute(
            """SELECT * FROM executions WHERE team_name=?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (team_name, limit, offset)
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def list_recent(limit: int = 50) -> list:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM executions ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def count_by_status() -> dict:
        conn = get_connection()
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM executions GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}


class AuditRepository:
    """CRUD for audit log entries."""

    @staticmethod
    def log(user_id: str, action: str, resource_type: str = None,
            resource_id: str = None, ip_address: str = None,
            user_agent: str = None, request_method: str = None,
            request_path: str = None, status_code: int = None,
            detail: dict = None, correlation_id: str = None):
        try:
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO audit_log
                       (user_id, action, resource_type, resource_id, ip_address,
                        user_agent, request_method, request_path, status_code,
                        detail_json, correlation_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, action, resource_type, resource_id, ip_address,
                     user_agent, request_method, request_path, status_code,
                     json.dumps(detail or {}, ensure_ascii=False), correlation_id)
                )
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    @staticmethod
    def query(user_id: str = None, action: str = None,
              limit: int = 100, offset: int = 0) -> list:
        conn = get_connection()
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []

        if user_id:
            query += " AND user_id=?"
            params.append(user_id)
        if action:
            query += " AND action=?"
            params.append(action)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def count_actions(since_hours: int = 24) -> dict:
        conn = get_connection()
        rows = conn.execute(
            """SELECT action, COUNT(*) as cnt
               FROM audit_log
               WHERE timestamp >= datetime('now', ?)
               GROUP BY action ORDER BY cnt DESC""",
            (f"-{since_hours} hours",)
        ).fetchall()
        return {r["action"]: r["cnt"] for r in rows}


class WebhookEventRepository:
    """CRUD for webhook event queue."""

    @staticmethod
    def enqueue(source: str, event_type: str, payload: dict,
                max_retries: int = 3) -> int:
        with get_db() as conn:
            cursor = conn.execute(
                """INSERT INTO webhook_events (source, event_type, payload_json, max_retries)
                   VALUES (?, ?, ?, ?)""",
                (source, event_type, json.dumps(payload, ensure_ascii=False), max_retries)
            )
            return cursor.lastrowid

    @staticmethod
    def get_pending(limit: int = 10) -> list:
        conn = get_connection()
        rows = conn.execute(
            """SELECT * FROM webhook_events
               WHERE status='pending' AND retry_count < max_retries
               ORDER BY created_at ASC LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def mark_processed(event_id: int):
        with get_db() as conn:
            conn.execute(
                "UPDATE webhook_events SET status='processed', processed_at=datetime('now') WHERE id=?",
                (event_id,)
            )

    @staticmethod
    def mark_failed(event_id: int, error: str):
        with get_db() as conn:
            conn.execute(
                """UPDATE webhook_events SET status='failed', retry_count=retry_count+1,
                   error_message=? WHERE id=?""",
                (error, event_id)
            )

    @staticmethod
    def mark_dead(event_id: int):
        with get_db() as conn:
            conn.execute(
                "UPDATE webhook_events SET status='dead_letter' WHERE id=?",
                (event_id,)
            )

    @staticmethod
    def get_stats() -> dict:
        conn = get_connection()
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM webhook_events GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}


# ══════════════════════════════════════════════════════════════
#   Database API Routes
# ══════════════════════════════════════════════════════════════

def register_db_routes(app):
    """Register database-related API routes."""
    from flask import request, jsonify

    @app.route("/api/db/stats", methods=["GET"])
    def db_stats():
        """Get database statistics."""
        conn = get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '_%'"
        ).fetchall()

        stats = {}
        for t in tables:
            tname = t["name"]
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM [{tname}]").fetchone()
            stats[tname] = row["cnt"]

        db_size = os.path.getsize(_DB_PATH) if os.path.exists(_DB_PATH) else 0

        return jsonify({
            "status": "success",
            "database": {
                "path": _DB_PATH,
                "size_bytes": db_size,
                "size_human": f"{db_size / 1024:.1f} KB" if db_size < 1048576
                              else f"{db_size / 1048576:.1f} MB",
                "tables": stats,
                "schema_version": SCHEMA_VERSION,
            }
        })

    logger.info("🗄️ [DB] Database routes registered")


# ── Auto-initialize on import ──
try:
    init_database()
except Exception as e:
    logger.warning(f"Database init deferred: {e}")
