# /// script
# requires-python = ">=3.12"
# dependencies = ["trailmark"]
# ///
"""Generate Mermaid diagrams from Trailmark code graphs.

Thin wrapper — all logic lives in ``trailmark.diagram``.
Run via ``uv run {this_file} --target ... --type ...``.
"""

from __future__ import annotations

import sys

from trailmark.diagram import main

if __name__ == "__main__":
    sys.exit(main())
