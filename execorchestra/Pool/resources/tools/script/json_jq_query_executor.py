"""S-GAR wrapper — jq (https://jqlang.github.io/jq, MIT).
Runs a real jq filter over a JSON file. argv: <file_path> [jq_filter] (default '.')."""
import sys
from _sgar_cli import run_cli, first_arg

f = first_arg("Usage: python json_jq_query_executor.py <file_path> [jq_filter]")
jq_filter = sys.argv[2] if len(sys.argv) > 2 else "."
run_cli("jq", ["jq", jq_filter, f], input_path=f, json_native=True, ok_returncodes=(0,))
