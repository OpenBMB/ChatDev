"""
SQLite-backed storage helpers for Vue graph editor payloads.
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional


_INITIALIZED_PATHS: set[Path] = set()


def _get_db_path() -> Path:
    """Resolve the SQLite database path, allowing overrides via env."""
    return Path(os.getenv("VUEGRAPHS_DB_PATH", "data/vuegraphs.db"))


def _ensure_db_initialized() -> Path:
    """Create the SQLite database and table if they do not already exist."""
    db_path = _get_db_path()
    if db_path not in _INITIALIZED_PATHS or not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS vuegraphs (
                    filename TEXT PRIMARY KEY,
                    content TEXT NOT NULL
                )
                """
            )
            connection.commit()
        _INITIALIZED_PATHS.add(db_path)
    return db_path


def save_vuegraph_content(filename: str, content: str) -> None:
    """Insert or update the stored content for the provided filename."""
    db_path = _ensure_db_initialized()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO vuegraphs (filename, content)
            VALUES (?, ?)
            ON CONFLICT(filename) DO UPDATE SET content=excluded.content
            """,
            (filename, content),
        )
        connection.commit()


def fetch_vuegraph_content(filename: str) -> Optional[str]:
    """Return the stored content for filename, or None when absent."""
    db_path = _ensure_db_initialized()
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            "SELECT content FROM vuegraphs WHERE filename = ?",
            (filename,),
        )
        row = cursor.fetchone()
        return row[0] if row else None
