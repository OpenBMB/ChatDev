"""S-GAR wrapper — gofmt (Go toolchain, https://go.dev, BSD).
Runs `gofmt -l -d` to report whether a Go source file is correctly formatted."""
from _sgar_cli import run_cli, first_arg

f = first_arg("Usage: python go_fmt_checker.py <file_path>")
# gofmt -l lists files that need formatting; -d shows the diff. Exit 0 always,
# so a non-empty stdout means "not formatted".
run_cli("gofmt", ["gofmt", "-l", "-d", f], input_path=f, ok_returncodes=(0,))
