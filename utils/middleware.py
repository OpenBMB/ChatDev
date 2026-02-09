"""Custom middleware for the DevAll workflow system."""

import uuid
from typing import Callable, Awaitable
from fastapi import Request, HTTPException, FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time
import re
import os

from utils.structured_logger import get_server_logger, LogType
from utils.exceptions import SecurityError


async def correlation_id_middleware(request: Request, call_next: Callable):
    """Add correlation ID to requests for tracing."""
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    # Log the request and response
    logger = get_server_logger()
    logger.log_request(
        request.method,
        str(request.url),
        correlation_id=correlation_id,
        path=request.url.path,
        query_params=dict(request.query_params),
        client_host=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    logger.log_response(
        response.status_code,
        duration,
        correlation_id=correlation_id,
        content_length=response.headers.get("content-length")
    )
    
    # Add correlation ID to response headers
    response.headers["X-Correlation-ID"] = correlation_id
    
    return response


async def security_middleware(request: Request, call_next: Callable):
    """Security middleware to validate requests."""
    # Validate content type for JSON endpoints
    if request.url.path.startswith("/api/") and request.method in ["POST", "PUT", "PATCH"]:
        content_type = request.headers.get("content-type", "").lower()
        if not content_type.startswith("application/json") and request.method != "GET":
            # Skip validation for file uploads
            if not content_type.startswith("multipart/form-data"):
                raise HTTPException(
                    status_code=400,
                    detail="Content-Type must be application/json for API endpoints"
                )
    
    # Validate file paths to prevent path traversal
    # Check URL path for suspicious patterns
    path = request.url.path
    if ".." in path or "./" in path:
        # Use a more thorough check
        if re.search(r"(\.{2}[/\\])|([/\\]\.{2})", path):
            logger = get_server_logger()
            logger.log_security_event(
                "PATH_TRAVERSAL_ATTEMPT",
                f"Suspicious path detected: {path}",
                correlation_id=getattr(request.state, 'correlation_id', str(uuid.uuid4()))
            )
            raise HTTPException(status_code=400, detail="Invalid path")
    
    response = await call_next(request)
    return response


async def rate_limit_middleware(request: Request, call_next: Callable):
    """Rate limiting middleware (basic implementation)."""
    # This is a simple rate limiting implementation
    # In production, you would use Redis or other storage for tracking
    # This is just a placeholder for now
    response = await call_next(request)
    return response


def add_cors_middleware(app: FastAPI) -> None:
    """Configure and attach CORS middleware."""
    # Dev defaults; override via CORS_ALLOW_ORIGINS (comma-separated)
    default_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    env_origins = os.getenv("CORS_ALLOW_ORIGINS")
    if env_origins:
        origins = [o.strip() for o in env_origins.split(",") if o.strip()]
        origin_regex = None
    else:
        origins = default_origins
        # Helpful in dev: allow localhost/127.0.0.1 on any port
        origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],
        max_age=600,
    )


def add_middleware(app: FastAPI):
    """Add all middleware to the FastAPI application."""
    # Attach CORS first to handle preflight requests and allow origins.
    add_cors_middleware(app)

    # Add other middleware
    app.middleware("http")(correlation_id_middleware)
    app.middleware("http")(security_middleware)
    # app.middleware("http")(rate_limit_middleware)  # Enable if needed
    
    return app
