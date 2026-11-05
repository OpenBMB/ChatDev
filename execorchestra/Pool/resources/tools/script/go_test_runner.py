"""S-GAR wrapper — go test (Go toolchain, https://go.dev, BSD).
Runs `go test ./...` for the Go module/package at <proj_dir>."""
import os
from _sgar_cli import run_cli, first_arg

d = first_arg("Usage: python go_test_runner.py <proj_dir>")
cwd = d if os.path.isdir(d) else os.path.dirname(os.path.abspath(d))
run_cli("go", ["go", "test", "./..."], input_path=d, cwd=cwd, timeout=300, ok_returncodes=(0,))
