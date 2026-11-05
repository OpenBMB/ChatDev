"""S-GAR wrapper — Stylelint + stylelint-config-standard (https://stylelint.io, MIT).
Runs the real `stylelint` CSS linter with the recognized standard ruleset and
native JSON output."""
import os
from _sgar_cli import run_cli, first_arg

f = first_arg("Usage: python stylelint_css_checker.py <file_path>")
cfg = os.environ.get("SGAR_STYLELINT_CONFIG", "/opt/stylelint.config.json")
argv = ["stylelint", "-f", "json", "--config", cfg,
        "--config-basedir", os.environ.get("NODE_PATH", "/usr/lib/node_modules"), f]
# stylelint exit 2 = lint problems found (a normal result, not a crash).
run_cli("stylelint", argv, input_path=f, json_native=True, ok_returncodes=(0, 1, 2))
