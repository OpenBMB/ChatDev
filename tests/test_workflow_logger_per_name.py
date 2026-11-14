"""Tests for per-workflow structured loggers.

``WorkflowLogger`` asks ``get_workflow_logger(self.workflow_id)`` for its
structured logger, so every workflow run needs its own logger: the run id is
part of the emitted JSON (``"logger"``) and of the default log file name
(``logs/<workflow_id>.log``). A process-wide singleton ignored the requested
name after the first call, so the second and every later workflow run logged
under the first run's name and appended to the first run's file.
"""

import utils.structured_logger as structured_logger
from utils.structured_logger import get_workflow_logger


class _RecordingLogger:
    """Stand-in that records how loggers are constructed, without touching disk."""

    def __init__(self, name, log_level, log_file=None):
        self.name = name
        self.log_level = log_level
        self.log_file = log_file


def test_workflow_loggers_are_independent_per_name(monkeypatch):
    created = []

    def factory(name, log_level, log_file=None):
        logger = _RecordingLogger(name, log_level, log_file)
        created.append(logger)
        return logger

    monkeypatch.setattr(structured_logger, "StructuredLogger", factory)
    monkeypatch.setattr(structured_logger, "_workflow_loggers", {}, raising=False)
    monkeypatch.delenv("WORKFLOW_LOG_FILE", raising=False)

    first = get_workflow_logger("run_alpha")
    second = get_workflow_logger("run_beta")
    first_again = get_workflow_logger("run_alpha")

    assert first is not second
    assert first is first_again
    assert [logger.name for logger in created] == ["run_alpha", "run_beta"]
    assert second.name == "run_beta"
    assert second.log_file == "logs/run_beta.log"
