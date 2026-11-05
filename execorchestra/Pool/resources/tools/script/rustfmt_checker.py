"""S-GAR wrapper — rustfmt (https://github.com/rust-lang/rustfmt, MIT/Apache-2.0).
Runs `rustfmt --check` to report whether a Rust source file is correctly formatted."""
from _sgar_cli import run_cli, first_arg

f = first_arg("Usage: python rustfmt_checker.py <file_path>")
# --check exits 0 if already formatted, 1 if a diff would be applied.
run_cli("rustfmt", ["rustfmt", "--check", "--edition", "2021", f], input_path=f)
