"""Regression tests for line-ending preservation in the file edit tool.

``apply_text_edits`` advertises ``newline="preserve"`` and reports the newline
style it wrote back, so an edit must not change how unrelated lines end. The text
mode used for reading and writing used to translate line breaks, which rewrote
LF files to CRLF, CRLF files to CR CR LF (Windows) and CR-only files to the
platform default line separator.
"""

from pathlib import Path

import pytest

from functions.function_calling.file import apply_text_edits
from utils.attachments import AttachmentStore


@pytest.fixture()
def workspace(tmp_path):
    run_root = tmp_path / "run"
    workspace_root = run_root / "code_workspace"
    workspace_root.mkdir(parents=True)
    context = {
        "attachment_store": AttachmentStore(run_root / "attachments"),
        "python_workspace_root": str(workspace_root),
        "graph_directory": str(run_root),
    }
    return workspace_root, context


def _apply_edit(workspace_root: Path, context: dict, *, encoding: str | None = None):
    params = {
        "start_line": 2,
        "end_line": 2,
        "replacement": "BETA",
        "_context": context,
    }
    if encoding is not None:
        params["encoding"] = encoding
    result = apply_text_edits("module.py", **params)
    return result, (workspace_root / "module.py").read_bytes()


@pytest.mark.parametrize(
    ("original", "expected", "newline"),
    [
        (b"alpha\nbeta\ngamma\n", b"alpha\nBETA\ngamma\n", "\n"),
        (b"alpha\r\nbeta\r\ngamma\r\n", b"alpha\r\nBETA\r\ngamma\r\n", "\r\n"),
        (b"alpha\rbeta\rgamma\r", b"alpha\rBETA\rgamma\r", "\r"),
    ],
)
def test_edit_preserves_existing_line_endings(workspace, original, expected, newline):
    workspace_root, context = workspace
    (workspace_root / "module.py").write_bytes(original)

    result, written = _apply_edit(workspace_root, context, encoding="utf-8")

    assert written == expected
    assert result["newline"] == newline


def test_auto_encoding_keeps_crlf_line_endings(workspace):
    """The default ``encoding="auto"`` path must not touch the line endings either."""
    workspace_root, context = workspace
    (workspace_root / "module.py").write_bytes(b"alpha\r\nbeta\r\ngamma\r\n")

    result, written = _apply_edit(workspace_root, context)

    assert written.count(b"\r\n") == 3
    assert b"\r\r\n" not in written
    assert written.replace(b"\xef\xbb\xbf", b"").split(b"\r\n") == [
        b"alpha",
        b"BETA",
        b"gamma",
        b"",
    ]
    assert result["newline"] == "\r\n"
