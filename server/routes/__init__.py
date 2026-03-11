"""Aggregates API routers."""

from . import artifacts, execute, execute_sync, health, sessions, uploads, vuegraphs, workflows, websocket, batch

ALL_ROUTERS = [
    health.router,
    vuegraphs.router,
    workflows.router,
    uploads.router,
    artifacts.router,
    sessions.router,
    batch.router,
    execute.router,
    execute_sync.router,
    websocket.router,
]

__all__ = ["ALL_ROUTERS"]