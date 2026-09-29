"""Tests for ``utils.function_manager`` dynamic module loading.

Regression coverage for issue #681: the dynamic loader executed tool
modules without registering them in ``sys.modules``, so a tool file
containing ``from __future__ import annotations`` and a dataclass failed
during class creation and ``FunctionManager`` silently dropped the whole
module's functions.
"""

import sys
from pathlib import Path

from utils.function_manager import FunctionManager


def _write_tool(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


def _modules_for(path: Path) -> dict:
    return {
        key: module
        for key, module in sys.modules.items()
        if key.startswith("_dynamic_functions.")
        and str(getattr(module, "__file__", "")) == str(path)
    }


def test_postponed_annotation_dataclass_tool_is_registered(tmp_path):
    """A dataclass with postponed annotations must not break the module load."""
    path = _write_tool(
        tmp_path,
        "example.py",
        """from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Payload:
    value: int


def increment(value: int) -> int:
    return Payload(value).value + 1
""",
    )

    manager = FunctionManager(tmp_path)

    assert manager.has_function("increment") is True
    assert manager.call_function("increment", 41) == 42
    assert len(_modules_for(path)) == 1


def test_failed_module_import_cleans_sys_modules(tmp_path):
    """A tool file that raises at import time must not leak a stale entry."""
    _write_tool(tmp_path, "broken.py", "raise RuntimeError('boom')\n")
    _write_tool(tmp_path, "healthy.py", "def work() -> int:\n    return 1\n")

    manager = FunctionManager(tmp_path)

    # The failing module is skipped without breaking its siblings.
    assert manager.has_function("work") is True
    leaked = [
        key
        for key in sys.modules
        if key.startswith("_dynamic_functions.") and "broken" in key
    ]
    assert leaked == []


def test_failed_reload_restores_previous_module_entry(tmp_path):
    """A failed reload must restore the previously registered module entry."""
    path = _write_tool(tmp_path, "example.py", "def value() -> int:\n    return 1\n")
    manager = FunctionManager(tmp_path)
    assert manager.has_function("value") is True
    registered = _modules_for(path)
    assert len(registered) == 1
    name, first_module = next(iter(registered.items()))

    path.write_text("raise RuntimeError('now broken')\n", encoding="utf-8")
    manager.reload_functions()
    assert manager.has_function("value") is False
    assert sys.modules.get(name) is first_module

    # A later successful reload replaces the restored entry.
    path.write_text("def value() -> int:\n    return 2\n", encoding="utf-8")
    manager.reload_functions()
    assert manager.has_function("value") is True
    assert manager.call_function("value") == 2
    assert sys.modules.get(name) is not first_module


def test_private_and_imported_functions_are_still_filtered(tmp_path):
    """Pre-existing filtering must survive the sys.modules registration."""
    _write_tool(
        tmp_path,
        "filters.py",
        """import os.path


def _helper() -> str:
    return "private"


def public_tool() -> str:
    return _helper()
""",
    )

    manager = FunctionManager(tmp_path)

    assert manager.has_function("public_tool") is True
    assert manager.has_function("_helper") is False
    assert manager.has_function("join") is False
