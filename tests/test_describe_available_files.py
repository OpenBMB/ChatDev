import json
from pathlib import Path

import pytest

from functions.function_calling.file import describe_available_files
from utils.attachments import AttachmentStore


def test_describe_available_files_json_serializable(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    attachments_dir = workspace_dir / "attachments"
    attachments_dir.mkdir()
    store = AttachmentStore(attachments_dir)

    sub_dir = workspace_dir / "subdir"
    sub_dir.mkdir()
    sample_file = sub_dir / "example.txt"
    sample_file.write_text("sample content", encoding="utf-8")

    context = {
        "python_workspace_root": workspace_dir,
        "attachment_store": store,
    }

    result = describe_available_files(_context=context)

    assert "files" in result
    entries = result["files"]
    assert len(entries) > 0

    # Ensure path and absolute_path are strictly str, not Path objects
    for entry in entries:
        assert isinstance(entry["path"], str)
        assert isinstance(entry["absolute_path"], str)
        assert not isinstance(entry["path"], Path)
        assert not isinstance(entry["absolute_path"], Path)

    # Must be JSON serializable without TypeError
    serialized = json.dumps(result)
    deserialized = json.loads(serialized)
    assert deserialized == result


def test_describe_available_files_limit_validation(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    store = AttachmentStore(workspace_dir / "attachments")

    context = {
        "python_workspace_root": workspace_dir,
        "attachment_store": store,
    }

    with pytest.raises(ValueError, match="limit must be positive"):
        describe_available_files(limit=0, _context=context)

    with pytest.raises(ValueError, match="limit must be positive"):
        describe_available_files(limit=-5, _context=context)


def test_describe_available_files_limit_truncation(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    store = AttachmentStore(workspace_dir / "attachments")

    (workspace_dir / "file1.txt").write_text("one", encoding="utf-8")
    (workspace_dir / "file2.txt").write_text("two", encoding="utf-8")
    (workspace_dir / "file3.txt").write_text("three", encoding="utf-8")

    context = {
        "python_workspace_root": workspace_dir,
        "attachment_store": store,
    }

    result = describe_available_files(limit=2, _context=context)
    assert len(result["files"]) <= 2


def test_describe_available_files_include_hidden(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    store = AttachmentStore(workspace_dir / "attachments")

    (workspace_dir / ".hidden.txt").write_text("secret", encoding="utf-8")
    (workspace_dir / "visible.txt").write_text("hello", encoding="utf-8")

    context = {
        "python_workspace_root": workspace_dir,
        "attachment_store": store,
    }

    result_hidden_false = describe_available_files(include_hidden=False, _context=context)
    names = [entry["name"] for entry in result_hidden_false["files"]]
    assert ".hidden.txt" not in names
    assert "visible.txt" in names

    result_hidden_true = describe_available_files(include_hidden=True, _context=context)
    names_all = [entry["name"] for entry in result_hidden_true["files"]]
    assert ".hidden.txt" in names_all
