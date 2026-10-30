"""Incoming dynamic edges must agree on the effective splitter settings."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from runtime import sdk
from utils.exceptions import WorkflowExecutionError


def _dynamic(
    split: dict[str, Any], *, mode: str = "map", **options: Any
) -> dict[str, Any]:
    return {"type": mode, "split": split, "config": options}


def _regex(**options: Any) -> dict[str, Any]:
    return {"type": "regex", "config": {"pattern": r"([a-z]+):(\d+)", **options}}


def _run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    first: dict[str, Any],
    second: dict[str, Any],
    *,
    contents: tuple[str, str] = ("alpha:1", "beta:2"),
) -> sdk.WorkflowRunResult:
    monkeypatch.chdir(tmp_path)
    # A literal target also allows successful tree controls to converge.
    target = (
        {"type": "literal", "config": {"content": "processed"}}
        if "tree" in (first["type"], second["type"])
        else {"type": "passthrough", "config": {"only_last_message": False}}
    )
    graph = {
        "id": "split_consistency",
        "nodes": [
            {"id": "a", "type": "literal", "config": {"content": contents[0]}},
            {"id": "b", "type": "literal", "config": {"content": contents[1]}},
            {"id": "target", **target},
        ],
        "edges": [
            {"from": "a", "to": "target", "dynamic": first},
            {"from": "b", "to": "target", "dynamic": second},
        ],
        "start": ["a", "b"],
        "end": ["target"],
    }
    workflow = tmp_path / "workflow.yaml"
    workflow.write_text(yaml.safe_dump({"graph": graph}), encoding="utf-8")
    return sdk.run_workflow(workflow, task_prompt="test")


def _target_texts(result: sdk.WorkflowRunResult) -> list[str]:
    assert result.meta_info.outputs is not None
    return sorted(
        item["payload"]["content"]
        for item in result.meta_info.outputs["node_target"]["results"]
    )


@pytest.mark.parametrize("mode", ["map", "tree"])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    ("first_options", "second_options"),
    [
        ({"group": 1}, {"group": 2}),
        ({"case_sensitive": True}, {"case_sensitive": False}),
        ({"multiline": False}, {"multiline": True}),
        ({"dotall": False}, {"dotall": True}),
        ({"on_no_match": "pass"}, {"on_no_match": "empty"}),
    ],
    ids=["group", "case_sensitive", "multiline", "dotall", "on_no_match"],
)
def test_reject_conflicting_regex_options_through_sdk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    reverse: bool,
    first_options: dict[str, Any],
    second_options: dict[str, Any],
) -> None:
    first = _dynamic(_regex(**first_options), mode=mode)
    second = _dynamic(_regex(**second_options), mode=mode)
    if reverse:
        first, second = second, first

    with pytest.raises(
        WorkflowExecutionError, match="inconsistent split configurations"
    ):
        _run(tmp_path, monkeypatch, first, second)


@pytest.mark.parametrize("group", [None, 0, "0"])
def test_explicit_regex_defaults_match_omitted_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, group: str | int | None
) -> None:
    result = _run(
        tmp_path,
        monkeypatch,
        _dynamic(_regex()),
        _dynamic(
            _regex(
                group=group,
                case_sensitive=True,
                multiline=False,
                dotall=False,
                on_no_match="pass",
            )
        ),
    )
    assert _target_texts(result) == ["alpha:1", "beta:2"]


def test_same_capture_group_from_different_config_paths_is_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Parsed edge/split paths differ, while numeric strings normalize to integers.
    result = _run(
        tmp_path,
        monkeypatch,
        _dynamic(_regex(group=2)),
        _dynamic(_regex(group="2")),
    )
    assert _target_texts(result) == ["1", "2"]


@pytest.mark.parametrize("split_type", ["message", "json_path"])
def test_nonregex_splits_ignore_irrelevant_regex_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, split_type: str
) -> None:
    config = {"json_path": "items"} if split_type == "json_path" else {}
    first = _dynamic({"type": split_type, "config": config})
    second = _dynamic(
        {
            "type": split_type,
            "config": {**config, "group": 2, "case_sensitive": False, "dotall": True},
        }
    )
    contents = ('{"items": ["alpha"]}', '{"items": ["beta"]}')
    result = _run(tmp_path, monkeypatch, first, second, contents=contents)
    expected = ["alpha", "beta"] if split_type == "json_path" else sorted(contents)
    assert _target_texts(result) == expected


def test_map_ignores_tree_only_group_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run(
        tmp_path,
        monkeypatch,
        _dynamic(_regex(group=1), group_size=2),
        _dynamic(_regex(group=1), group_size=9),
    )
    assert _target_texts(result) == ["alpha", "beta"]


@pytest.mark.parametrize(
    ("first", "second", "error"),
    [
        (_dynamic(_regex()), _dynamic({"type": "message"}), "inconsistent split"),
        (
            _dynamic(_regex()),
            _dynamic(_regex(pattern=r"(\w+):(\d+)")),
            "inconsistent split",
        ),
        (
            _dynamic({"type": "json_path", "config": {"json_path": "items"}}),
            _dynamic({"type": "json_path", "config": {"json_path": "other"}}),
            "inconsistent split",
        ),
        (_dynamic(_regex()), _dynamic(_regex(), mode="tree"), "inconsistent dynamic"),
        (
            _dynamic(_regex(), max_parallel=1),
            _dynamic(_regex(), max_parallel=2),
            "inconsistent max_parallel",
        ),
        (
            _dynamic(_regex(), mode="tree", group_size=2),
            _dynamic(_regex(), mode="tree", group_size=3),
            "inconsistent group_size",
        ),
    ],
    ids=["split_type", "pattern", "json_path", "mode", "max_parallel", "group_size"],
)
def test_existing_dynamic_mismatch_checks_still_reject(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    first: dict[str, Any],
    second: dict[str, Any],
    error: str,
) -> None:
    with pytest.raises(WorkflowExecutionError, match=error):
        _run(tmp_path, monkeypatch, first, second)
