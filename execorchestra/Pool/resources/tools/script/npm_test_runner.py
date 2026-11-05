"""S-GAR wrapper — npm test (https://docs.npmjs.com, Artistic-2.0). Runs `npm test` in <proj_dir>."""
import os
from _sgar_cli import run_cli, first_arg

d = first_arg("Usage: python npm_test_runner.py <proj_dir>")
cwd = d if os.path.isdir(d) else os.path.dirname(os.path.abspath(d))
run_cli("npm", ["npm", "test"], input_path=d, cwd=cwd, timeout=300, ok_returncodes=(0, 1))
