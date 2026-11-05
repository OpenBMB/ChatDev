"""S-GAR tool — HTML→Markdown via markdownify (https://github.com/matthewwithanm/python-markdownify, MIT)."""
import sys
import os
from _sgar_cli import emit
from markdownify import markdownify as md

if len(sys.argv) < 2:
    print("Usage: python html_to_markdown_converter.py <file_path>", file=sys.stderr)
    sys.exit(1)
path = sys.argv[1]
if not os.path.exists(path):
    emit({"status": "error", "message": f"{path} not found"})
    sys.exit(2)
with open(path, encoding="utf-8") as fh:
    html = fh.read()
emit({"status": "success", "tool": "markdownify", "target": path,
      "markdown": md(html, heading_style="ATX")})
