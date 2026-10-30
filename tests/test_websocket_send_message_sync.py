"""Tests for WebSocketManager.send_message_sync cross-thread safety.

Verifies that send_message_sync correctly delivers messages when called
from worker threads (the common case during workflow execution).

Load the manager in isolation without leaving dependency stubs in sys.modules.
"""

import asyncio
import concurrent.futures
import importlib.util
import json
import sys
import threading
import time
from pathlib import Path
from types import ModuleType
from typing import List
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Isolate WebSocketManager from the circular-import chain
# ---------------------------------------------------------------------------


@pytest.fixture
def make_manager(monkeypatch):
    service_name = "server.services.workflow_run_service"
    service_stub = ModuleType(service_name)
    service_stub.WorkflowRunService = MagicMock()
    spec = importlib.util.spec_from_file_location(
        "websocket_manager_under_test",
        Path(__file__).resolve().parents[1] / "server/services/websocket_manager.py",
    )
    module = importlib.util.module_from_spec(spec)
    # Only the workflow runner needs isolation. In particular, keep the real
    # in-memory session store so snapshots and reconnect behavior are realistic.
    with monkeypatch.context() as isolated:
        isolated.setitem(sys.modules, service_name, service_stub)
        spec.loader.exec_module(module)

    def create_manager():
        return module.WebSocketManager(
            session_store=module.WorkflowSessionStore(),
            session_controller=MagicMock(),
            attachment_service=MagicMock(),
            workflow_run_service=MagicMock(),
        )

    return create_manager


class FakeWebSocket:
    """Lightweight fake that records sent messages and the thread they arrived on."""

    def __init__(self) -> None:
        self.sent: List[str] = []
        self.send_threads: List[int] = []

    async def accept(self) -> None:
        pass

    async def send_text(self, data: str) -> None:
        self.sent.append(data)
        self.send_threads.append(threading.get_ident())

    async def close(self, **kwargs) -> None:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSendMessageSync:
    """send_message_sync must deliver messages regardless of calling thread."""

    def test_send_from_main_thread(self, make_manager):
        """Message sent from the main (event-loop) thread is delivered."""
        manager = make_manager()
        ws = FakeWebSocket()
        delivered = []

        async def run():
            sid = await manager.connect(ws, session_id="s1")
            # Drain the initial "connection" message
            ws.sent.clear()

            manager.send_message_sync(sid, {"type": "test", "data": "hello"})
            # Give the scheduled coroutine a moment to execute
            await asyncio.sleep(0.05)
            delivered.extend(ws.sent)

        # Waiting on a thread-safe Future from its own loop would deadlock.
        # Fail immediately if that path is used, rather than waiting 10 seconds.
        with patch.object(concurrent.futures.Future, "result") as blocking_wait:
            asyncio.run(run())
        blocking_wait.assert_not_called()
        assert len(delivered) == 1
        assert '"test"' in delivered[0]

    def test_send_from_worker_thread(self, make_manager):
        """Message sent from a background (worker) thread is delivered on the owner loop."""
        manager = make_manager()
        ws = FakeWebSocket()
        worker_errors: List[Exception] = []

        async def run():
            sid = await manager.connect(ws, session_id="s2")
            ws.sent.clear()
            main_thread = threading.get_ident()

            def worker():
                try:
                    manager.send_message_sync(sid, {"type": "from_worker"})
                except Exception as exc:
                    worker_errors.append(exc)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(worker)
                # Let the worker thread finish and the scheduled coro run
                while not future.done():
                    await asyncio.sleep(0.01)
                future.result()  # re-raise if worker threw
                await asyncio.sleep(0.1)

            # Verify delivery
            assert len(ws.sent) == 1, f"Expected 1 message, got {len(ws.sent)}"
            assert '"from_worker"' in ws.sent[0]

            # Verify send_text ran on the main loop thread, not the worker
            assert ws.send_threads[0] == main_thread

        asyncio.run(run())
        assert not worker_errors, f"Worker thread raised: {worker_errors}"

    def test_concurrent_workers_no_lost_messages(self, make_manager):
        """Multiple concurrent workers should each have their message delivered.

        In production, the event loop is free while workers run (the main coroutine
        awaits ``run_in_executor``).  We replicate that by polling workers via
        ``asyncio.sleep`` so the loop can process the scheduled sends.
        """
        manager = make_manager()
        ws = FakeWebSocket()
        num_workers = 8

        async def run():
            sid = await manager.connect(ws, session_id="s3")
            ws.sent.clear()

            barrier = threading.Barrier(num_workers)
            done_flags = [False] * num_workers

            def worker(idx: int):
                barrier.wait(timeout=5)
                manager.send_message_sync(sid, {"type": "msg", "idx": idx})
                done_flags[idx] = True

            pool = concurrent.futures.ThreadPoolExecutor(max_workers=num_workers)
            futures = [pool.submit(worker, i) for i in range(num_workers)]

            # Yield control so the loop can process sends while workers run
            deadline = time.time() + 15
            while not all(done_flags) and time.time() < deadline:
                await asyncio.sleep(0.05)

            # Collect any worker exceptions
            for f in futures:
                f.result(timeout=1)

            # Let remaining coros drain
            await asyncio.sleep(0.3)
            pool.shutdown(wait=False)

            assert len(ws.sent) == num_workers, (
                f"Expected {num_workers} messages, got {len(ws.sent)}"
            )
            assert sorted(json.loads(message)["idx"] for message in ws.sent) == list(range(num_workers))

        asyncio.run(run())


class TestSessionReconnect:
    def test_reconnect_replays_messages_and_serializes_snapshot(self, make_manager):
        manager = make_manager()
        session = manager.session_store.create_session(
            session_id="reconnect", yaml_file="test.yaml", task_prompt="test",
        )
        buffered = {"type": "test", "data": "buffered"}
        session.append_message(buffered)
        ws = FakeWebSocket()

        async def run():
            assert await manager.connect(ws, session_id=session.session_id) == session.session_id

        asyncio.run(run())
        messages = [json.loads(message) for message in ws.sent]
        assert [message["type"] for message in messages] == ["connection", "test", "session_resumed"]
        assert messages[1] == buffered
        assert messages[2]["data"]["session_id"] == session.session_id
        assert messages[2]["data"]["status"] == "idle"
        assert messages[2]["data"]["message_count"] == 1

    def test_send_after_disconnect_does_not_crash(self, make_manager):
        """Sending after disconnection should not raise."""
        manager = make_manager()
        ws = FakeWebSocket()

        async def run():
            sid = await manager.connect(ws, session_id="s4")
            manager.disconnect(sid)

            # Should silently skip, not crash
            manager.send_message_sync(sid, {"type": "late"})
            await asyncio.sleep(0.05)

        asyncio.run(run())  # no exception == pass

    def test_send_before_any_connection_no_crash(self, make_manager):
        """Calling send_message_sync before any connect() should not crash."""
        manager = make_manager()
        # _owner_loop is None
        manager.send_message_sync("nonexistent", {"type": "orphan"})
        # Should log a warning, not crash


class TestOwnerLoopCapture:
    """The manager must capture the event loop on first connect."""

    def test_owner_loop_captured_on_connect(self, make_manager):
        manager = make_manager()
        ws = FakeWebSocket()

        async def run():
            assert manager._owner_loop is None
            await manager.connect(ws, session_id="cap1")
            assert manager._owner_loop is asyncio.get_running_loop()

        asyncio.run(run())

    def test_owner_loop_stable_across_connections(self, make_manager):
        """Subsequent connects should not reset the owner loop."""
        manager = make_manager()
        ws1 = FakeWebSocket()
        ws2 = FakeWebSocket()

        async def run():
            await manager.connect(ws1, session_id="cap2")
            loop1 = manager._owner_loop
            await manager.connect(ws2, session_id="cap3")
            assert manager._owner_loop is loop1

        asyncio.run(run())
