"""S-GAR tool — JSON → TOML via tomli-w (https://github.com/hukkin/tomli-w, MIT)."""
import sys
import os
import json
from _sgar_cli import emit
import tomli_w

if len(sys.argv) < 2:
    print("Usage: python json_to_toml_converter.py <file_path>", file=sys.stderr)
    sys.exit(1)
path = sys.argv[1]
if not os.path.exists(path):
    emit({"status": "error", "message": f"{path} not found"})
    sys.exit(2)
try:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        emit({"status": "error", "message": "TOML root must be a JSON object"})
        sys.exit(1)
    emit({"status": "success", "tool": "tomli-w", "target": path, "toml": tomli_w.dumps(data)})
except json.JSONDecodeError as exc:
    emit({"status": "error", "tool": "tomli-w", "message": f"invalid JSON: {exc}"})
    sys.exit(1)
