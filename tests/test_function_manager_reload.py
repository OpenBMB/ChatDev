import os
import py_compile
from pathlib import Path

from utils.function_manager import FunctionManager


def test_reload_reads_edited_source_with_unchanged_cache_metadata(tmp_path: Path):
    tool = tmp_path / "tool.py"
    tool.write_text("def value(): return 1\n", encoding="utf-8")
    os.utime(tool, (1_700_000_000, 1_700_000_000))
    manager = FunctionManager(tmp_path)
    assert manager.call_function("value") == 1

    tool.write_text("def value(): return 2\n", encoding="utf-8")
    os.utime(tool, (1_700_000_000, 1_700_000_000))
    manager.reload_functions()
    assert manager.call_function("value") == 2
    assert list(manager.list_functions()) == ["value"]


def test_new_manager_reads_source_instead_of_an_existing_bytecode_cache(tmp_path: Path):
    tool = tmp_path / "tool.py"
    tool.write_text("def value(): return 1\n", encoding="utf-8")
    os.utime(tool, (1_700_000_000, 1_700_000_000))
    py_compile.compile(str(tool), doraise=True)
    tool.write_text("def value(): return 2\n", encoding="utf-8")
    os.utime(tool, (1_700_000_000, 1_700_000_000))

    assert FunctionManager(tmp_path).call_function("value") == 2


def test_reload_keeps_encoding_and_function_filtering(tmp_path: Path):
    tool = tmp_path / "tool.py"
    tool.write_bytes(
        b"# coding: latin-1\nfrom os.path import basename\n"
        b"def label(): return 'caf\xe9'\ndef _private(): return 0\n"
    )
    manager = FunctionManager(tmp_path)
    assert manager.call_function("label") == "café"
    assert list(manager.list_functions()) == ["label"]
    tool.unlink()
    manager.reload_functions()
    assert manager.list_functions() == {}
