import argparse
import logging
from pathlib import Path

from runtime.bootstrap.schema import ensure_schema_registry_populated
from server.app import app


ensure_schema_registry_populated()


# Directories containing the server's Python sources. When --reload is
# enabled, only these are watched so that agent-generated files under
# WareHouse/, logs/, etc. never trigger a StatReload restart mid-workflow
# (issue #569).
RELOAD_SOURCE_DIRS = [
    "check",
    "entity",
    "functions",
    "mcp_example",
    "runtime",
    "schema_registry",
    "server",
    "tools",
    "utils",
    "workflow",
]

# Glob patterns excluded from reload watching. Only has effect when
# ``watchfiles`` is installed (StatReload ignores these patterns), but
# matches .gitignore intent as a second line of defence.
RELOAD_EXCLUDES = [
    "WareHouse/*",
    "logs/*",
    "data/*",
    "temp/*",
    "node_modules/*",
]


def build_reload_kwargs(args: argparse.Namespace) -> dict:
    """Build the reload-related kwargs passed to ``uvicorn.run``.

    Extracted so the configuration is unit-testable without spinning up
    a real server. When ``--reload`` is off the return value is empty.
    """
    if not args.reload:
        return {}
    return {
        "reload_dirs": list(args.reload_dir) if args.reload_dir else list(RELOAD_SOURCE_DIRS),
        "reload_excludes": list(args.reload_exclude) if args.reload_exclude else list(RELOAD_EXCLUDES),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DevAll Workflow Server")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Server host (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port (default: 8000)"
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="Log level (default: info)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--reload-dir",
        action="append",
        default=None,
        metavar="DIR",
        help=(
            "Directory to watch when --reload is active (repeatable). "
            "Defaults to the server's Python source folders, which excludes "
            "WareHouse/ and other output dirs."
        ),
    )
    parser.add_argument(
        "--reload-exclude",
        action="append",
        default=None,
        metavar="GLOB",
        help=(
            "Glob pattern excluded from reload watching (repeatable). "
            "Requires watchfiles to take effect."
        ),
    )
    return parser


def main():
    import uvicorn

    args = build_parser().parse_args()

    # Configure structured logging
    import os
    os.environ['LOG_LEVEL'] = args.log_level.upper()

    # Ensure log directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "server.log"),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Starting DevAll Workflow Server on {args.host}:{args.port}")

    # Launch the server
    uvicorn.run(
        "server.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
        ws="wsproto",
        **build_reload_kwargs(args),
    )


if __name__ == "__main__":
    main()
