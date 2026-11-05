"""Batch failures retain causes without leaking SDK exception messages."""
from io import StringIO

import httpx
from loguru import logger
from openai import APIConnectionError

from sgar_mvp.src import terminal_progress


def test_batch_diagnostics_keep_local_cause_but_not_sensitive_message(monkeypatch):
    monkeypatch.setattr(terminal_progress, "_console", None)
    secret = "diagnostic-sentinel-not-for-logs"
    request = httpx.Request("POST", "https://invalid.test/v1/chat/completions",
                            headers={"Authorization": "Bearer " + secret})
    error = APIConnectionError(request=request)
    error.__cause__ = RuntimeError("Cannot send request: " + secret)
    sink = StringIO()
    sink_id = logger.add(sink, format="{message}")
    try:
        terminal_progress.transport_detail(error)
    finally:
        logger.remove(sink_id)
    logged = sink.getvalue()
    assert "APIConnectionError" in logged
    assert "RuntimeError" in logged
    assert secret not in logged
    assert "invalid.test" not in logged


def test_batch_diagnostics_distinguish_protocol_disconnect(monkeypatch):
    monkeypatch.setattr(terminal_progress, "_console", None)
    request = httpx.Request("POST", "https://invalid.test/v1/chat/completions")
    error = APIConnectionError(request=request)
    error.__cause__ = httpx.RemoteProtocolError("private response detail", request=request)
    sink = StringIO()
    sink_id = logger.add(sink, format="{message}")
    try:
        terminal_progress.transport_detail(error)
    finally:
        logger.remove(sink_id)
    assert "RemoteProtocolError" in sink.getvalue()
    assert "private response detail" not in sink.getvalue()
