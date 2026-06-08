"""Utilities for loading reusable subgraph YAML definitions."""

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple

from entity.configs import ConfigError
from utils.io_utils import read_yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_SUBGRAPH_ROOT = (_REPO_ROOT / "yaml_instance").resolve()
# Cache parsed subgraphs keyed on the resolved path, alongside the file's
# mtime at load time so an on-disk edit invalidates the cached copy (see #622).
_SUBGRAPH_CACHE: Dict[Path, Tuple[float, Dict[str, Any]]] = {}


def _resolve_candidate_paths(file_path: str, parent_source: str | None) -> List[Path]:
    path = Path(file_path)
    if path.is_absolute():
        return [path]

    candidates: List[Path] = []
    default_candidate = (_DEFAULT_SUBGRAPH_ROOT / path).resolve()
    candidates.append(default_candidate)

    if parent_source:
        parent = Path(parent_source)
        parent_dir = parent.parent if parent.is_file() else parent
        candidates.append((parent_dir / path).resolve())

    # As a last resort, allow relative to repo root / current working dir
    candidates.append((_REPO_ROOT / path).resolve())
    return candidates


def _resolve_existing_path(candidates: List[Path]) -> Path:
    checked: List[str] = []
    for candidate in candidates:
        checked.append(str(candidate))
        if candidate.exists():
            return candidate
    raise ConfigError(
        f"subgraph YAML not found; tried: {', '.join(checked)}",
        path=checked[-1] if checked else None,
    )


def _load_graph_dict(path: Path) -> Dict[str, Any]:
    data = read_yaml(path)
    if not isinstance(data, dict):
        raise ConfigError("subgraph YAML root must be a mapping", path=str(path))

    graph_block = data.get("graph")
    if graph_block is None:
        graph_block = data

    if not isinstance(graph_block, dict):
        raise ConfigError("subgraph graph section must be a mapping", path=f"{path}.graph")

    vars_block = data.get("vars") if isinstance(data.get("vars"), dict) else {}

    return {"graph": graph_block, "vars": vars_block}


def load_subgraph_config(file_path: str, *, parent_source: str | None = None) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """Load a subgraph definition from disk.

    Returns a tuple of (graph_dict, resolved_path).
    """

    candidates = _resolve_candidate_paths(file_path, parent_source)
    resolved_path = _resolve_existing_path(candidates).resolve()

    mtime = resolved_path.stat().st_mtime
    cached = _SUBGRAPH_CACHE.get(resolved_path)
    if cached is None or cached[0] != mtime:
        _SUBGRAPH_CACHE[resolved_path] = (mtime, _load_graph_dict(resolved_path))

    payload = _SUBGRAPH_CACHE[resolved_path][1]
    graph_dict = deepcopy(payload["graph"])
    vars_dict = dict(payload["vars"])
    return graph_dict, vars_dict, str(resolved_path)


__all__ = ["load_subgraph_config"]
