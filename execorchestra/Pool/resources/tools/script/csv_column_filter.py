"""S-GAR tool — CSV column projection via pandas (https://pandas.pydata.org, BSD).
Keeps only the requested columns (comma-separated) from a CSV file."""
import sys
import os
import io
from _sgar_cli import emit
import pandas as pd

if len(sys.argv) < 3:
    print("Usage: python csv_column_filter.py <file_path> <columns_to_filter>", file=sys.stderr)
    sys.exit(1)
path, cols_arg = sys.argv[1], sys.argv[2]
if not os.path.exists(path):
    emit({"status": "error", "message": f"{path} not found"})
    sys.exit(2)
cols = [c.strip() for c in cols_arg.split(",") if c.strip()]
try:
    df = pd.read_csv(path)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        emit({"status": "error", "tool": "pandas",
              "message": f"columns not found: {missing}", "available": list(df.columns)})
        sys.exit(1)
    out = df[cols]
    buf = io.StringIO()
    out.to_csv(buf, index=False)
    emit({"status": "success", "tool": "pandas", "target": path,
          "kept_columns": cols, "row_count": len(out), "csv": buf.getvalue()})
except Exception as exc:
    emit({"status": "error", "tool": "pandas", "message": f"{type(exc).__name__}: {exc}"})
    sys.exit(1)
