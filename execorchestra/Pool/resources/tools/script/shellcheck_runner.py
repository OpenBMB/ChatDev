"""S-GAR wrapper — ShellCheck (https://www.shellcheck.net, GPLv3).
Invokes the real `shellcheck` CLI (native JSON diagnostics)."""
from _sgar_cli import run_cli, first_arg

f = first_arg("Usage: python shellcheck_runner.py <file_path>")
run_cli("shellcheck", ["shellcheck", "-f", "json", f], input_path=f, json_native=True)
