"""S-GAR tool — JSON→YAML conversion via PyYAML (https://pyyaml.org, MIT)."""
import sys
import os
import json
import yaml
from _sgar_cli import emit

if len(sys.argv) < 2:
    print("Usage: python json_to_yaml.py <file_path>", file=sys.stderr)
    sys.exit(1)
path = sys.argv[1]
if not os.path.exists(path):
    emit({"status": "error", "message": f"{path} not found"})
    sys.exit(2)
try:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    out = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    emit({"status": "success", "tool": "PyYAML", "target": path, "yaml": out})
except json.JSONDecodeError as exc:
    emit({"status": "error", "tool": "PyYAML", "message": f"invalid JSON: {exc}"})
    sys.exit(1)
