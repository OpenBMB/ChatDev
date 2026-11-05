"""S-GAR tool — Markdown→HTML via Python-Markdown (https://python-markdown.github.io, BSD)."""
import sys
import os
from _sgar_cli import emit
import markdown

if len(sys.argv) < 2:
    print("Usage: python markdown_to_html_converter.py <file_path>", file=sys.stderr)
    sys.exit(1)
path = sys.argv[1]
if not os.path.exists(path):
    emit({"status": "error", "message": f"{path} not found"})
    sys.exit(2)
with open(path, encoding="utf-8") as fh:
    src = fh.read()
html = markdown.markdown(src, extensions=["tables", "fenced_code", "toc"])
emit({"status": "success", "tool": "python-markdown", "target": path, "html": html})
