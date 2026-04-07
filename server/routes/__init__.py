"""Aggregates API routers."""

from . import artifacts, batch, execute, execute_sync, health, sessions, skills, tools, triggers, uploads, vuegraphs, websocket, workflows

ALL_ROUTERS = [
    health.router,
    vuegraphs.router,
    workflows.router,
    uploads.router,
    artifacts.router,
    sessions.router,
    batch.router,
    skills.router,
    execute.router,
    execute_sync.router,
    triggers.router,
    tools.router,
    websocket.router,
]

__all__ = ["ALL_ROUTERS"]
