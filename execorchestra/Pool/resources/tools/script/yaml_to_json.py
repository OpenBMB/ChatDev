"""S-GAR tool — YAML→JSON conversion via PyYAML (https://pyyaml.org, MIT).
Parses a YAML file with the recognized PyYAML library and emits JSON."""
import sys
import os
import json
import yaml
from _sgar_cli import emit

if len(sys.argv) < 2:
    print("Usage: python yaml_to_json.py <file_path>", file=sys.stderr)
    sys.exit(1)
path = sys.argv[1]
if not os.path.exists(path):
    emit({"status": "error", "message": f"{path} not found"})
    sys.exit(2)
try:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    emit({"status": "success", "tool": "PyYAML", "target": path, "json": data})
except yaml.YAMLError as exc:
    emit({"status": "error", "tool": "PyYAML", "message": f"invalid YAML: {exc}"})
    sys.exit(1)
