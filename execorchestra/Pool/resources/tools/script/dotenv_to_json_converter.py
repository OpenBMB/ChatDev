"""S-GAR tool — .env → JSON via python-dotenv (https://github.com/theskumar/python-dotenv, BSD)."""
import sys
import os
from _sgar_cli import emit
from dotenv import dotenv_values

if len(sys.argv) < 2:
    print("Usage: python dotenv_to_json_converter.py <file_path>", file=sys.stderr)
    sys.exit(1)
path = sys.argv[1]
if not os.path.exists(path):
    emit({"status": "error", "message": f"{path} not found"})
    sys.exit(2)
values = dict(dotenv_values(path))
emit({"status": "success", "tool": "python-dotenv", "target": path,
      "key_count": len(values), "json": values})
