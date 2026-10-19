"""Regression tests for runtime package import side effects."""

import subprocess
import sys


def test_check_module_imports_without_runtime_circular_import():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from check.check import load_config; assert callable(load_config)",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
