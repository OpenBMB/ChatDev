from pathlib import Path

import pytest
from functions.function_calling.file import search_in_files
from utils.attachments import AttachmentStore


def _make_context(workspace: Path) -> dict:
    attachments_dir = workspace / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    store = AttachmentStore(attachments_dir)
    return {
        "python_workspace_root": workspace,
        "attachment_store": store,
    }


def test_search_in_files_empty_pattern(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    (tmp_path / "sample.txt").write_text("hello world\n", encoding="utf-8")

    with pytest.raises(ValueError, match="pattern cannot be empty"):
        search_in_files("", _context=context)


def test_search_in_files_invalid_regex(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    (tmp_path / "sample.txt").write_text("hello [world]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid regular expression pattern"):
        search_in_files("[", use_regex=True, _context=context)

    with pytest.raises(ValueError, match="Invalid regular expression pattern"):
        search_in_files("*unmatched", use_regex=True, _context=context)


def test_search_in_files_context_bounds_validation(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    (tmp_path / "sample.txt").write_text("line1\nline2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="before_context must be non-negative"):
        search_in_files("line", before_context=-1, _context=context)

    with pytest.raises(ValueError, match="after_context must be non-negative"):
        search_in_files("line", after_context=-2, _context=context)


def test_search_in_files_max_results_validation(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    (tmp_path / "sample.txt").write_text("line1\nline2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="max_results must be positive"):
        search_in_files("line", max_results=0, _context=context)

    with pytest.raises(ValueError, match="max_results must be positive"):
        search_in_files("line", max_results=-5, _context=context)


def test_search_in_files_regex_matching(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    (tmp_path / "sample.py").write_text(
        "def test_foo():\n    pass\n\ndef test_bar():\n    pass\n",
        encoding="utf-8",
    )

    result = search_in_files(r"def test_\w+\(\):", use_regex=True, _context=context)
    assert result["limited"] is False
    assert len(result["matches"]) == 2
    assert result["matches"][0]["line"] == 1
    assert result["matches"][0]["line_text"] == "def test_foo():"
    assert result["matches"][1]["line"] == 4
    assert result["matches"][1]["line_text"] == "def test_bar():"


def test_search_in_files_literal_with_context(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    (tmp_path / "data.txt").write_text(
        "first\nsecond\ntarget\nfourth\nfifth\n",
        encoding="utf-8",
    )

    result = search_in_files(
        "target",
        use_regex=False,
        before_context=2,
        after_context=1,
        _context=context,
    )
    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["line"] == 3
    assert match["line_text"] == "target"
    assert match["before"] == ["first", "second"]
    assert match["after"] == ["fourth"]
