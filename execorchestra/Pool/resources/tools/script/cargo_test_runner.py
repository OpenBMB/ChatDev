"""S-GAR wrapper — cargo test (Rust toolchain, https://doc.rust-lang.org/cargo, MIT/Apache-2.0).
Runs `cargo test` for the Rust project at <proj_dir>."""
import os
from _sgar_cli import run_cli, first_arg

d = first_arg("Usage: python cargo_test_runner.py <proj_dir>")
cwd = d if os.path.isdir(d) else os.path.dirname(os.path.abspath(d))
run_cli("cargo", ["cargo", "test"], input_path=d, cwd=cwd, timeout=300, ok_returncodes=(0,))
