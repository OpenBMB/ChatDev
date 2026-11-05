"""S-GAR wrapper — pip-audit (https://github.com/pypa/pip-audit, Apache-2.0).
Audits Python dependencies for known vulnerabilities (PyPI Advisory / OSV).
argv: [requirements.txt]  — if omitted, audits the current environment."""
import sys
import os
from _sgar_cli import run_cli

if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
    req = sys.argv[1]
    argv = ["pip-audit", "-r", req, "-f", "json"]
    inp = req
else:
    argv = ["pip-audit", "-f", "json"]
    inp = None
# pip-audit exits 1 when vulnerabilities are found (a normal audit result).
run_cli("pip-audit", argv, input_path=inp, json_native=True, timeout=300, ok_returncodes=(0, 1))
