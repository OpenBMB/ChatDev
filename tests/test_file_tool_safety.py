from pathlib import Path

import pytest

from functions.function_calling.file import (
    apply_text_edits,
    copy_path,
    create_folder,
    delete_path,
    move_path,
    rename_path,
    save_file,
)
from utils.attachments import AttachmentStore


def _make_context(workspace: Path) -> dict:
    attachments_dir = workspace / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    store = AttachmentStore(attachments_dir)
    return {
        "python_workspace_root": workspace,
        "attachment_store": store,
    }


@pytest.mark.parametrize(
    "blocked_path",
    [
        "attachments",
        "attachments/file.txt",
        "./attachments",
        "./attachments/file.txt",
        "sub/../attachments/file.txt",
    ],
)
def test_attachments_guard_rejects_mutations(tmp_path: Path, blocked_path: str) -> None:
    context = _make_context(tmp_path)
    err_msg = "Modifications to the attachments directory are not allowed"

    with pytest.raises(ValueError, match=err_msg):
        create_folder(blocked_path, _context=context)

    with pytest.raises(ValueError, match=err_msg):
        delete_path(blocked_path, _context=context)

    with pytest.raises(ValueError, match=err_msg):
        save_file(blocked_path, "payload", _context=context)

    with pytest.raises(ValueError, match=err_msg):
        apply_text_edits(blocked_path, start_line=1, replacement="test", _context=context)

    with pytest.raises(ValueError, match=err_msg):
        rename_path(blocked_path, "other.txt", _context=context)

    with pytest.raises(ValueError, match=err_msg):
        rename_path("other.txt", blocked_path, _context=context)

    with pytest.raises(ValueError, match=err_msg):
        copy_path("other.txt", blocked_path, _context=context)

    with pytest.raises(ValueError, match=err_msg):
        move_path(blocked_path, "other.txt", _context=context)

    with pytest.raises(ValueError, match=err_msg):
        move_path("other.txt", blocked_path, _context=context)


def test_attachments_guard_allows_safe_paths(tmp_path: Path) -> None:
    context = _make_context(tmp_path)

    # Filename containing 'attachments' substring or directory with attachments as child
    res = save_file("safe_attachments.txt", "content", _context=context)
    assert res["path"] == "safe_attachments.txt"
    assert (tmp_path / "safe_attachments.txt").read_text(encoding="utf-8") == "content"


def test_delete_path_rejects_workspace_root(tmp_path: Path) -> None:
    context = _make_context(tmp_path)

    with pytest.raises(ValueError, match="Cannot delete the workspace root directory"):
        delete_path(".", recursive=True, _context=context)

    with pytest.raises(ValueError, match="Cannot delete the workspace root directory"):
        delete_path("./", recursive=True, _context=context)

    assert tmp_path.exists()


def test_rename_and_move_reject_workspace_root(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    (tmp_path / "sample.txt").write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError, match="Cannot rename the workspace root directory"):
        rename_path(".", "renamed", _context=context)

    with pytest.raises(ValueError, match="Cannot overwrite the workspace root directory"):
        rename_path("sample.txt", ".", _context=context)

    with pytest.raises(ValueError, match="Cannot move the workspace root directory"):
        move_path(".", "moved", _context=context)

    with pytest.raises(ValueError, match="Cannot overwrite the workspace root directory"):
        move_path("sample.txt", ".", _context=context)


def test_copy_path_rejects_overwriting_workspace_root(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    (tmp_path / "sample.txt").write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError, match="Cannot overwrite the workspace root directory"):
        copy_path("sample.txt", ".", _context=context)
