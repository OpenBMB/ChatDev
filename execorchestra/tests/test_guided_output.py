"""Check the guided view against actual logging events and final audit status."""
import io
from types import SimpleNamespace

from loguru import logger
import pytest

from sgar_mvp.src import terminal_progress as progress


class NamedStream(io.StringIO):
    name = "progress.log"


@pytest.fixture
def sinks(monkeypatch):
    screen, guide = io.StringIO(), NamedStream()
    console = progress.Console(screen, guide)
    monkeypatch.setattr(progress, "_console", console)
    sink_id = logger.add(console, format="{message}")
    try:
        yield screen, guide, console
    finally:
        logger.remove(sink_id)


def test_guided_log_preserves_step_purpose_and_output(sinks, monkeypatch):
    screen, guide, _ = sinks
    monkeypatch.setenv("SERVICE_API_KEY", "private-sentinel-abc")
    logger.bind(terminal_task="t1").info(
        "[ResourcePlan] Executing count with python (Tool) | step_type=run_tool | intent=Count rows"
    )
    progress.step_output("t1", SimpleNamespace(step_id="count", output_key="row_count"),
                         '{"count":7,"token":"private-sentinel-abc"}')
    for stream in (screen, guide):
        text = stream.getvalue()
        for fragment in ("t1", "Count rows", "count", "row_count", '"count": 7'):
            assert fragment in text
        assert "private-sentinel-abc" not in text


def test_verbose_terminal_keeps_guided_log_readable(sinks):
    screen, guide, console = sinks
    console.verbose = True
    progress.detail("Compiler", "Input; attempt 1; message 2", {"wire_schema": "schema-marker"})
    assert "schema-marker" in screen.getvalue()
    assert "Preparing the plan" in guide.getvalue()
    assert "schema-marker" not in guide.getvalue()


def test_failed_audit_does_not_announce_a_delivery(sinks, tmp_path):
    screen, guide, _ = sinks
    (tmp_path / "final_output.json").write_text('{"sum":42}')
    (tmp_path / "delivery_manifest.json").write_text('{"delivery_locator":"final_output.json"}')
    failure = SimpleNamespace(failure_stage="terminal_audit", failure_code="invalid_report",
                              responsibility="framework", exception_type="")
    manifest = SimpleNamespace(manifest_valid=True, pipeline_succeeded=False,
                               primary_failure=failure, terminal_failure=failure)
    progress.final_summary("structured_failure", tmp_path, tmp_path / "report.md",
                           tmp_path / "pipeline.log", manifest=manifest)
    for stream in (screen, guide):
        text = stream.getvalue()
        assert "Run failed" in text and "invalid_report" in text
        assert "Delivered file" not in text

def test_profiler_handoff_names_the_task_and_deliverable():
    handoff = progress._detail_view("Profiler", "Starting; complete input", {
        "envelope_sha256": "internal-schema-digest",
        "subtask": {"description": "Calculate the total", "expected_output": "A JSON file"},
    })
    assert "Calculate the total" in handoff and "A JSON file" in handoff
    assert "internal-schema-digest" not in handoff


@pytest.mark.parametrize("match", [True, False])
def test_delivered_content_comes_from_the_published_file(sinks, tmp_path, match):
    import hashlib
    import json
    raw = b'{"total": 17}'
    (tmp_path / "out.json").write_bytes(raw)
    (tmp_path / "delivery_manifest.json").write_text(json.dumps({
        "delivery_locator": "out.json",
        "content_sha256": hashlib.sha256(raw if match else b"older").hexdigest(),
    }))
    progress.final_summary("complete_success", tmp_path, tmp_path / "report.md",
                           tmp_path / "pipeline.log",
                           manifest=SimpleNamespace(manifest_valid=True, pipeline_succeeded=True))
    for stream in sinks[:2]:
        assert ('[Delivered content] {"total": 17}' in stream.getvalue()) == match
