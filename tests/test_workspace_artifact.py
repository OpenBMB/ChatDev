import logging

from utils.attachments import AttachmentStore
from workflow.hooks.workspace_artifact import WorkspaceArtifactHook


def test_snapshot_logs_counts_when_scan_is_truncated(tmp_path, caplog):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "artifact.txt").write_text("payload", encoding="utf-8")

    hook = WorkspaceArtifactHook(
        attachment_store=AttachmentStore(tmp_path / "attachments"),
        emit_callback=lambda _: None,
        max_files_scanned=1,
    )

    with caplog.at_level(logging.WARNING, logger=hook.logger.name):
        snapshot, truncated = hook._snapshot(workspace)

    assert truncated is True
    assert set(snapshot) == {"artifact.txt"}
    assert caplog.messages == ["Workspace scan truncated (files=1 total_bytes=7)"]
