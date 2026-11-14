"""``python -m check.check --path <yaml>``: exit 0 only for a workflow ``load_config`` accepts."""

import subprocess
import sys
from pathlib import Path

import pytest

from check.check import main

REPO = Path(__file__).resolve().parents[1]
UNKNOWN_NODE_TYPE = """\
version: 0.4.0
graph:
  id: bad
  start: [A]
  end: [A]
  nodes:
    - id: A
      type: no_such_node_type
      config: {}
  edges: []
"""


def test_valid_workflow_prints_ok_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--path", str(REPO / "yaml_instance" / "demo_loop_counter.yaml")]) == 0
    assert "Workflow OK." in capsys.readouterr().out


def test_missing_file_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--path", str(tmp_path / "absent.yaml")]) == 1
    out = capsys.readouterr().out
    assert "absent.yaml" in out and "Workflow OK." not in out


def test_unknown_node_type_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(UNKNOWN_NODE_TYPE)
    assert main(["--path", str(path)]) == 1
    assert "no_such_node_type" in capsys.readouterr().out


def test_module_entry_point_exits_non_zero_on_a_missing_file(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "check.check", "--path", str(tmp_path / "absent.yaml")],
        check=False, cwd=REPO, capture_output=True, text=True,
    )
    assert proc.returncode == 1 and "absent.yaml" in proc.stdout


def test_load_config_is_importable_first_in_a_fresh_interpreter() -> None:
    """``check.check -> runtime.bootstrap.schema -> runtime -> runtime.sdk -> check.check`` must not cycle."""
    proc = subprocess.run(
        [sys.executable, "-c", "from check.check import load_config"],
        check=False, cwd=REPO, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
