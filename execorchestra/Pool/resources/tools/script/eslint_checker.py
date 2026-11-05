"""S-GAR wrapper — ESLint (https://eslint.org, MIT).
Lints a JS/TS file with the real eslint CLI (recommended flat config), native JSON."""
import os
from _sgar_cli import run_cli, first_arg

f = first_arg("Usage: python eslint_checker.py <file_path>")
cfg = os.environ.get("SGAR_ESLINT_CONFIG", "/opt/eslint.config.mjs")
run_cli("eslint", ["eslint", "-f", "json", "--no-config-lookup", "--config", cfg, f],
        input_path=f, json_native=True, ok_returncodes=(0, 1))
