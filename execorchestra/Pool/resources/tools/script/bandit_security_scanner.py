"""S-GAR wrapper — Bandit security scanner (https://bandit.readthedocs.io, Apache-2.0). Native JSON."""
from _sgar_cli import run_cli, first_arg

f = first_arg("Usage: python bandit_security_scanner.py <file_or_dir>")
run_cli("bandit", ["bandit", "-r", f, "-f", "json"],
        input_path=f, json_native=True, ok_returncodes=(0, 1))
