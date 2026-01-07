"""Aggregates API routers."""

from . import artifacts, execute, health, sessions, uploads, vuegraphs, workflows, websocket

ALL_ROUTERS = [
    health.router,
    vuegraphs.router,
    workflows.router,
    uploads.router,
    artifacts.router,
    sessions.router,
    execute.router,
    websocket.router,
]

__all__ = ["ALL_ROUTERS"]
