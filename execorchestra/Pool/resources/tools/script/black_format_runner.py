"""S-GAR wrapper — Black formatter (https://black.readthedocs.io, MIT).
Runs `black --check --diff` to report whether a file is correctly formatted."""
from _sgar_cli import run_cli, first_arg

f = first_arg("Usage: python black_format_runner.py <file_path>")
run_cli("black", ["black", "--check", "--diff", f], input_path=f, ok_returncodes=(0, 1))
