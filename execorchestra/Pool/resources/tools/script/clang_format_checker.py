"""S-GAR wrapper — clang-format (https://clang.llvm.org/docs/ClangFormat.html, Apache-2.0).
Runs `clang-format --dry-run --Werror` to report whether a C/C++/… source file
is correctly formatted (exit 1 = would reformat)."""
from _sgar_cli import run_cli, first_arg

f = first_arg("Usage: python clang_format_checker.py <file_path>")
run_cli("clang-format", ["clang-format", "--dry-run", "--Werror", f], input_path=f)
