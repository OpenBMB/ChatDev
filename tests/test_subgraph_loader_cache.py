"""Tests for ``workflow.subgraph_loader`` cache invalidation.

Regression coverage for issue #622: editing a subgraph YAML that has already
been loaded, then loading it again in the same process, must return the *new*
on-disk content. The original implementation cached parsed subgraphs in a
module-level dict keyed only on the resolved file path, with no staleness
check, so a subgraph stayed stale until ChatDev was restarted.
"""

import importlib
import os
from pathlib import Path

import pytest

import workflow.subgraph_loader as subgraph_loader


@pytest.fixture(autouse=True)
def _clear_cache():
    """Start each test with an empty module-level cache."""
    importlib.reload(subgraph_loader)
    yield


def _write_subgraph(path: Path, node_name: str) -> None:
    path.write_text(
        "graph:\n"
        "  nodes:\n"
        f"    - name: {node_name}\n"
        "vars:\n"
        "  answer: 1\n",
        encoding="utf-8",
    )


def test_reload_after_edit_returns_new_content(tmp_path: Path):
    subgraph = tmp_path / "subgraph.yaml"
    _write_subgraph(subgraph, "v1")

    graph_dict, _vars, _resolved = subgraph_loader.load_subgraph_config(str(subgraph))
    assert graph_dict["nodes"][0]["name"] == "v1"

    # Edit the file in place, bumping mtime to defeat coarse filesystem clocks.
    _write_subgraph(subgraph, "v2")
    stat = subgraph.stat()
    os.utime(subgraph, (stat.st_atime + 1, stat.st_mtime + 1))

    graph_dict, _vars, _resolved = subgraph_loader.load_subgraph_config(str(subgraph))
    assert graph_dict["nodes"][0]["name"] == "v2", (
        "subgraph_loader served a stale cached copy after the file was edited"
    )


def test_unchanged_file_is_served_from_cache(tmp_path: Path, monkeypatch):
    """An unedited file must not be re-parsed on every load (cache preserved)."""
    subgraph = tmp_path / "subgraph.yaml"
    _write_subgraph(subgraph, "v1")

    subgraph_loader.load_subgraph_config(str(subgraph))

    calls = {"count": 0}
    original = subgraph_loader._load_graph_dict

    def _counting(path):
        calls["count"] += 1
        return original(path)

    monkeypatch.setattr(subgraph_loader, "_load_graph_dict", _counting)

    subgraph_loader.load_subgraph_config(str(subgraph))
    subgraph_loader.load_subgraph_config(str(subgraph))
    assert calls["count"] == 0, "unchanged subgraph should be served from cache"
