"""S-GAR wrapper — Jest (https://jestjs.io, MIT). Runs `jest --json` in <proj_dir>."""
import os
from _sgar_cli import run_cli, first_arg

d = first_arg("Usage: python jest_test_runner.py <proj_dir>")
cwd = d if os.path.isdir(d) else os.path.dirname(os.path.abspath(d))
run_cli("jest", ["jest", "--json"], input_path=d, cwd=cwd,
        json_native=True, timeout=180, ok_returncodes=(0, 1))
