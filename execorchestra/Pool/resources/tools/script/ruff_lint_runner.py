"""S-GAR wrapper — Ruff linter (https://docs.astral.sh/ruff, MIT). Native JSON output."""
from _sgar_cli import run_cli, first_arg

f = first_arg("Usage: python ruff_lint_runner.py <file_path>")
run_cli("ruff", ["ruff", "check", "--output-format", "json", f],
        input_path=f, json_native=True, ok_returncodes=(0, 1))
