"""S-GAR tool — XLSX→CSV extraction via openpyxl (https://openpyxl.readthedocs.io, MIT).
Reads a real .xlsx workbook with the recognized openpyxl library and emits each
sheet as CSV text."""
import sys
import os
import io
import csv
from _sgar_cli import emit
import openpyxl

if len(sys.argv) < 2:
    print("Usage: python xlsx2csv.py <file_path>", file=sys.stderr)
    sys.exit(1)
path = sys.argv[1]
if not os.path.exists(path):
    emit({"status": "error", "message": f"{path} not found"})
    sys.exit(2)
try:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheets = {}
    for ws in wb.worksheets:
        buf = io.StringIO()
        writer = csv.writer(buf)
        for row in ws.iter_rows(values_only=True):
            writer.writerow(["" if c is None else c for c in row])
        sheets[ws.title] = buf.getvalue()
    emit({"status": "success", "tool": "openpyxl", "target": path,
          "sheet_names": list(sheets.keys()), "sheets_csv": sheets})
except Exception as exc:  # openpyxl raises various errors for bad workbooks
    emit({"status": "error", "tool": "openpyxl", "message": f"{type(exc).__name__}: {exc}"})
    sys.exit(1)
