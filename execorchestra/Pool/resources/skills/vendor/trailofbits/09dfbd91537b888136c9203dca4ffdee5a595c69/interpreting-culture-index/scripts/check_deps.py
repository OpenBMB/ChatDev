#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check that all dependencies for Culture Index extraction are installed.

Usage:
    uv run check_deps.py

Exit codes:
    0 - All dependencies installed
    1 - Missing dependencies (details printed to stderr)
"""

from __future__ import annotations

import shutil
import sys


def check_python_packages() -> list[str]:
    """Check for required Python packages.

    Returns:
        List of missing package names.
    """
    missing = []

    try:
        import cv2  # noqa: F401
    except ImportError:
        missing.append("opencv-python-headless")

    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")

    try:
        import pdf2image  # noqa: F401
    except ImportError:
        missing.append("pdf2image")

    try:
        import pytesseract  # noqa: F401
    except ImportError:
        missing.append("pytesseract")

    return missing


def check_system_deps() -> list[str]:
    """Check for required system dependencies.

    Returns:
        List of missing system dependency names.
    """
    missing = []

    # Check for poppler (pdftoppm command)
    if not shutil.which("pdftoppm"):
        missing.append("poppler")

    # Check for tesseract
    if not shutil.which("tesseract"):
        missing.append("tesseract")

    return missing


def main() -> int:
    """Check all dependencies and report status.

    Returns:
        Exit code (0 = success, 1 = missing dependencies).
    """
    missing_python = check_python_packages()
    missing_system = check_system_deps()

    if not missing_python and not missing_system:
        print("All dependencies installed.", file=sys.stderr)
        return 0

    print("Missing dependencies:", file=sys.stderr)

    if missing_python:
        print(f"\n  Python packages: {', '.join(missing_python)}", file=sys.stderr)
        print("  Install with: uv pip install .", file=sys.stderr)

    if missing_system:
        print(f"\n  System tools: {', '.join(missing_system)}", file=sys.stderr)
        if "poppler" in missing_system:
            print(
                "    poppler: brew install poppler (macOS) or apt install poppler-utils",
                file=sys.stderr,
            )
        if "tesseract" in missing_system:
            print(
                "    tesseract: brew install tesseract (macOS) or apt install tesseract-ocr",
                file=sys.stderr,
            )

    return 1


if __name__ == "__main__":
    sys.exit(main())
