"""Application bootstrap helpers for the FastAPI server."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server import state
from server.config_schema_router import router as config_schema_router
from server.routes import ALL_ROUTERS
from utils.error_handler import add_exception_handlers
from utils.middleware import add_middleware


def init_app(app: FastAPI) -> None:
    """Apply shared middleware, routers, and global state to ``app``."""

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    add_exception_handlers(app)
    add_middleware(app)

    state.init_state()

    for router in ALL_ROUTERS:
        app.include_router(router)

    app.include_router(config_schema_router)
