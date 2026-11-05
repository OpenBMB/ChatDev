"""S-GAR wrapper — npm audit (https://docs.npmjs.com/cli/commands/npm-audit, Artistic-2.0).
Audits the dependencies declared in a package.json project using the real npm CLI."""
import os
from _sgar_cli import run_cli, first_arg

f = first_arg("Usage: python npm_package_auditor.py <package.json_or_dir>")
proj_dir = f if os.path.isdir(f) else os.path.dirname(os.path.abspath(f))
run_cli("npm", ["npm", "audit", "--json", "--prefix", proj_dir],
        input_path=f, json_native=True, timeout=180, ok_returncodes=(0, 1))
