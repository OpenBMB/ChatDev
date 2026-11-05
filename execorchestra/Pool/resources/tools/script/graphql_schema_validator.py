"""S-GAR tool — GraphQL SDL validation via graphql-core (https://github.com/graphql-python/graphql-core, MIT).
Parses and builds a GraphQL schema from an SDL file using the recognized
reference implementation; reports syntax/validation errors."""
import sys
import os
from _sgar_cli import emit
from graphql import build_schema
from graphql.error import GraphQLError

if len(sys.argv) < 2:
    print("Usage: python graphql_schema_validator.py <file_path>", file=sys.stderr)
    sys.exit(1)
path = sys.argv[1]
if not os.path.exists(path):
    emit({"status": "error", "message": f"{path} not found"})
    sys.exit(2)
with open(path, encoding="utf-8") as fh:
    sdl = fh.read()
try:
    schema = build_schema(sdl)
    types = [t for t in schema.type_map if not t.startswith("__")]
    emit({"status": "success", "tool": "graphql-core", "target": path,
          "valid": True, "type_count": len(types), "types": types})
except GraphQLError as exc:
    emit({"status": "success", "tool": "graphql-core", "target": path,
          "valid": False, "error": str(exc)})
    sys.exit(1)
