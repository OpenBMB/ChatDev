#!/usr/bin/env python3
"""Extract text from a local document with upstream Trafilatura."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import trafilatura


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract text from local HTML/XML")
    parser.add_argument("input_path")
    parser.add_argument("--output-format", choices=("txt", "markdown", "json"), default="txt")
    parser.add_argument("--max-bytes", type=int, default=5_000_000)
    args = parser.parse_args()
    path = Path(args.input_path).resolve()
    try:
        raw = path.read_bytes()
        if len(raw) > args.max_bytes:
            raise ValueError("input exceeds max_bytes")
        extracted = trafilatura.extract(raw.decode("utf-8", errors="replace"), output_format=args.output_format)
        if extracted is None:
            extracted = ""
        result = {
            "status": "success",
            "tool": "trafilatura",
            "target": str(path),
            "output_format": args.output_format,
            "text": extracted,
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "tool": "trafilatura", "target": str(path), "message": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
