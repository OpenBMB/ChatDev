"""S-GAR wrapper — npm audit (https://docs.npmjs.com/cli/commands/npm-audit, Artistic-2.0).
Runs `npm audit --json` for the project directory containing the given
package.json (or a directory path) using the real npm CLI."""
import os
from _sgar_cli import run_cli, first_arg

f = first_arg("Usage: python npm_audit_json_exporter.py <package.json_or_dir>")
proj_dir = f if os.path.isdir(f) else os.path.dirname(os.path.abspath(f))
# npm audit exits non-zero when vulnerabilities are found; treat 0/1 as a run.
run_cli("npm", ["npm", "audit", "--json", "--prefix", proj_dir],
        input_path=f, json_native=True, timeout=180, ok_returncodes=(0, 1))
