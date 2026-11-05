"""S-GAR wrapper — go test coverage (Go toolchain, https://go.dev, BSD).
Runs `go test -cover` for the Go package/module at <path> (a directory, or a
file whose directory is used) and reports per-package coverage."""
import sys
import os
import subprocess
from _sgar_cli import emit, first_arg

f = first_arg("Usage: python go_test_coverage.py <package_dir_or_file>")
if not os.path.exists(f):
    emit({"status": "error", "message": f"{f} not found"})
    sys.exit(2)
workdir = f if os.path.isdir(f) else os.path.dirname(os.path.abspath(f))
res = subprocess.run(["go", "test", "-cover", "./..."], cwd=workdir,
                     capture_output=True, text=True, encoding="utf-8",
                     errors="replace", timeout=300)
lines = [ln for ln in (res.stdout + res.stderr).splitlines() if ln.strip()]
emit({"status": "success", "tool": "go test", "target": workdir,
      "exit_code": res.returncode, "passed": res.returncode == 0, "output": lines})
