"""S-GAR wrapper — Flake8 (https://flake8.pycqa.org, MIT).
Runs the real flake8 linter over a file/dir and returns its findings."""
from _sgar_cli import run_cli, first_arg

f = first_arg("Usage: python flake8_lint_runner.py <target_path>")
run_cli("flake8", ["flake8", f], input_path=f, ok_returncodes=(0, 1))
