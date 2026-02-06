import argparse
import logging
from pathlib import Path

from runtime.bootstrap.schema import ensure_schema_registry_populated
from server.app import app


ensure_schema_registry_populated()


def main():
    import uvicorn

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
    
    args = parser.parse_args()

    # Configure structured logging
    import os
    os.environ['LOG_LEVEL'] = args.log_level.upper()
    os.environ['CHATDEV_SERVER_PORT'] = str(args.port)
    
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
    )


if __name__ == "__main__":
    main()
