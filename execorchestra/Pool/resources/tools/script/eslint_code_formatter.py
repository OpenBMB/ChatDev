"""S-GAR wrapper — ESLint (https://eslint.org, MIT).
Lints a JS/TS file with the real eslint CLI and returns native JSON diagnostics.
Uses a minimal recommended config so it runs without a project .eslintrc."""
import os
from _sgar_cli import run_cli, first_arg

f = first_arg("Usage: python eslint_code_formatter.py <file_path>")
# --no-config-lookup + inline flat recommended config keeps it project-independent.
cfg = os.environ.get("SGAR_ESLINT_CONFIG", "/opt/eslint.config.mjs")
argv = ["eslint", "-f", "json", "--no-config-lookup", "--config", cfg, f]
run_cli("eslint", argv, input_path=f, json_native=True, ok_returncodes=(0, 1))
