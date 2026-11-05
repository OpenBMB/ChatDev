"""S-GAR wrapper — TypeScript compiler `tsc --noEmit` (https://www.typescriptlang.org, Apache-2.0).
Type-checks the TS project at <project_dir> (must contain tsconfig.json)."""
import sys
import os
from _sgar_cli import run_cli, first_arg

p = first_arg("Usage: python tsc_compile_runner.py <project_dir>")
cwd = p if os.path.isdir(p) else os.path.dirname(os.path.abspath(p))
run_cli("tsc", ["tsc", "--noEmit"], input_path=p, cwd=cwd, ok_returncodes=(0,))
