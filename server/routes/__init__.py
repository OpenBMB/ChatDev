"""Aggregates API routers."""

from . import (
    artifacts, batch, execute, health, internal,
    sessions, uploads, vuegraphs, workflows, websocket,
)

ALL_ROUTERS = [
    health.router,
    vuegraphs.router,
    workflows.router,
    uploads.router,
    artifacts.router,
    sessions.router,
    batch.router,
    execute.router,
    websocket.router,
    internal.router,
]

__all__ = ["ALL_ROUTERS"]
