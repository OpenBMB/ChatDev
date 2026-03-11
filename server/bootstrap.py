from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server import state
from server.config_schema_router import router as config_schema_router
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