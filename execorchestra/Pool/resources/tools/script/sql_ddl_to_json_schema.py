"""S-GAR tool — SQL DDL → JSON schema via sqlglot (https://github.com/tobymao/sqlglot, MIT).
Parses CREATE TABLE statements with the recognized sqlglot SQL parser and emits
each table's columns and types."""
import sys
import os
from _sgar_cli import emit
import sqlglot
from sqlglot import exp

if len(sys.argv) < 2:
    print("Usage: python sql_ddl_to_json_schema.py <file_path>", file=sys.stderr)
    sys.exit(1)
path = sys.argv[1]
if not os.path.exists(path):
    emit({"status": "error", "message": f"{path} not found"})
    sys.exit(2)
with open(path, encoding="utf-8") as fh:
    ddl = fh.read()
try:
    tables = []
    for stmt in sqlglot.parse(ddl):
        if isinstance(stmt, exp.Create) and stmt.args.get("kind") == "TABLE":
            tname = stmt.this.this.name if stmt.this and stmt.this.this else None
            cols = []
            for c in stmt.find_all(exp.ColumnDef):
                constraints = [type(cc.kind).__name__ for cc in c.constraints] if c.constraints else []
                cols.append({"name": c.name, "type": c.args["kind"].sql() if c.args.get("kind") else None,
                             "constraints": constraints})
            tables.append({"table": tname, "columns": cols})
    emit({"status": "success", "tool": "sqlglot", "target": path, "tables": tables})
except sqlglot.errors.ParseError as exc:
    emit({"status": "error", "tool": "sqlglot", "message": f"parse error: {exc}"})
    sys.exit(1)
