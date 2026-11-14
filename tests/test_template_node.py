"""Template node and template edge processor, run offline through the SDK (literal sources, no model calls)."""

from pathlib import Path

import pytest

import runtime.sdk as sdk
from runtime.sdk import run_workflow

WORKFLOW = """\
version: 0.4.0
graph:
  id: template_test
  start: [Src]
  end: [Report, Edge]
  nodes:
    - id: Src
      type: literal
      config:
        content: '{"name": "Ana", "findings": ["fever", "cough"]}'
        role: user
    - id: Report
      type: template
      config:
        template: "{% set d = input | fromjson %}{{ d.name }}:{{ d.findings | join(',') }}"
    - id: Edge
      type: passthrough
      config: {}
  edges:
    - from: Src
      to: Report
    - from: Src
      to: Edge
      process:
        type: template
        config:
          template: "{{ (input | fromjson).name | upper }}"
"""


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> dict:
    monkeypatch.setattr(sdk, "OUTPUT_ROOT", tmp_path / "out")
    path = tmp_path / "wf.yaml"
    path.write_text(text)
    result = run_workflow(str(path), task_prompt="go")
    return {
        node_id: out["results"][-1]["payload"]["content"]
        for node_id, out in ((k.removeprefix("node_"), v) for k, v in result.meta_info.outputs.items())
        if isinstance(out, dict) and out.get("results")
    }


def test_node_and_edge_processor_render(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outputs = _run(tmp_path, monkeypatch, WORKFLOW)
    assert outputs["Report"] == "Ana:fever,cough"
    assert outputs["Edge"] == "ANA"


def test_undefined_variable_fails_and_lists_available_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    broken = WORKFLOW.replace("{{ d.name }}", "{{ environment.run_id }}")
    with pytest.raises(Exception, match="Available context keys: input"):
        _run(tmp_path, monkeypatch, broken)
