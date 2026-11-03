"""Tests for ``utils.function_manager.FunctionManager`` dynamic imports.

Regression coverage for issue #681: dynamically loaded tool modules were
executed without being registered in ``sys.modules``. Any tool file that
creates a dataclass under postponed annotations (``from __future__ import
annotations``) then fails during class creation, because the dataclass
decorator resolves the defining module through ``sys.modules``, and
``FunctionManager`` silently drops the whole module's functions.
"""

import sys
from pathlib import Path

from utils.function_manager import FunctionManager


def test_postponed_annotation_dataclass_tool_is_loaded(tmp_path: Path):
    tool = tmp_path / "dataclass_tool.py"
    tool.write_text(
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class Payload:\n"
        "    value: int\n"
        "\n"
        "\n"
        "def make(value: int) -> int:\n"
        "    return Payload(value=value).value\n",
        encoding="utf-8",
    )
    manager = FunctionManager(tmp_path)

    assert manager.has_function("make")
    assert manager.call_function("make", 41) == 41
    assert list(manager.list_functions()) == ["make"]


def test_failed_import_is_skipped_without_leaking_sys_modules(tmp_path: Path):
    good = tmp_path / "good.py"
    good.write_text("def ok():\n    return 'ok'\n", encoding="utf-8")
    bad = tmp_path / "bad.py"
    bad.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    manager = FunctionManager(tmp_path)

    assert manager.call_function("ok") == "ok"
    assert manager.list_functions() == {"ok": manager.get_function("ok")}
    assert manager._build_module_name(bad) not in sys.modules


def test_failed_reload_restores_previous_module_registration(tmp_path: Path):
    tool = tmp_path / "tool.py"
    tool.write_text("def value():\n    return 1\n", encoding="utf-8")
    manager = FunctionManager(tmp_path)
    assert manager.call_function("value") == 1
    module_name = manager.get_function("value").__module__
    registered = sys.modules[module_name]

    # The replacement must differ in size so the timestamp/size bytecode
    # cache is invalidated and the new source is actually executed.
    tool.write_text("raise RuntimeError('boom')\n# changed size\n", encoding="utf-8")
    manager.reload_functions()

    assert manager.list_functions() == {}
    # The failed exec must neither replace the previously registered module
    # nor leave the partially initialized one behind.
    assert sys.modules.get(module_name) is registered
