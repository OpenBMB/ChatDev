"""Regression tests for text encoding detection in the file tools.

``encoding="auto"`` used to resolve to ``utf-8-sig`` for every UTF-8 payload,
including files without a byte-order mark. The encoding is echoed back to the
caller and reused by ``apply_text_edits``, so a plain UTF-8 file received a BOM
after its first edit.
"""

from pathlib import Path

import pytest

from functions.function_calling.file import apply_text_edits, read_file_segment
from utils.attachments import AttachmentStore

UTF8_BOM = b"\xef\xbb\xbf"


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


def _normalize_newlines(payload: bytes) -> bytes:
    return payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def test_bomless_utf8_file_does_not_gain_a_bom(workspace):
    workspace_root, context = workspace
    target = workspace_root / "setup.py"
    target.write_bytes(b'print("hello")\n')

    result = apply_text_edits(
        "setup.py",
        start_line=1,
        end_line=1,
        replacement='print("bye")',
        _context=context,
    )

    written = target.read_bytes()
    assert result["encoding"] == "utf-8"
    assert UTF8_BOM not in written
    assert _normalize_newlines(written) == b'print("bye")\n'


def test_utf8_bom_file_keeps_a_single_bom(workspace):
    workspace_root, context = workspace
    target = workspace_root / "bom.py"
    target.write_bytes(UTF8_BOM + b'print("hello")\n')

    result = apply_text_edits(
        "bom.py",
        start_line=1,
        end_line=1,
        replacement='print("bye")',
        _context=context,
    )

    written = target.read_bytes()
    assert result["encoding"] == "utf-8-sig"
    assert written.startswith(UTF8_BOM)
    assert written.count(UTF8_BOM) == 1
    assert _normalize_newlines(written[len(UTF8_BOM):]) == b'print("bye")\n'


def test_read_file_segment_reports_the_detected_encoding(workspace):
    workspace_root, context = workspace
    (workspace_root / "plain.py").write_bytes(b"alpha\nbeta\n")
    (workspace_root / "marked.py").write_bytes(UTF8_BOM + b"alpha\nbeta\n")

    plain = read_file_segment("plain.py", start_line=1, line_count=1, _context=context)
    marked = read_file_segment("marked.py", start_line=1, line_count=1, _context=context)

    assert plain["encoding"] == "utf-8"
    assert marked["encoding"] == "utf-8-sig"
