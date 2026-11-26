"""The workspace scan truncation warning must be formattable."""

import logging
from unittest.mock import Mock

from workflow.hooks.workspace_artifact import WorkspaceArtifactHook


def test_truncated_scan_warning_is_formattable(tmp_path, caplog):
    for index in range(3):
        (tmp_path / f"file_{index}.txt").write_text("data")

    hook = WorkspaceArtifactHook(
        attachment_store=Mock(),
        emit_callback=Mock(),
        max_files_scanned=1,
    )

    with caplog.at_level(logging.WARNING):
        _, truncated = hook._snapshot(tmp_path)

    assert truncated is True
    messages = [record.getMessage() for record in caplog.records]
    assert any("Workspace scan truncated" in message for message in messages)
    assert any(str(tmp_path) in message for message in messages)
