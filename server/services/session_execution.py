"""Human input coordination for workflow sessions."""

import concurrent.futures
import logging
import time
from concurrent.futures import Future
from typing import Any, Dict, Optional

from utils.exceptions import ValidationError, TimeoutError as CustomTimeoutError, WorkflowCancelledError
from utils.structured_logger import LogType, get_server_logger

from .session_store import SessionStatus, WorkflowSessionStore


class SessionExecutionController:
    """Handles blocking wait/provide cycles for human input."""

    def __init__(self, store: WorkflowSessionStore) -> None:
        self.store = store
        self.logger = logging.getLogger(__name__)

    def set_waiting_for_input(self, session_id: str, node_id: str, input_data: Dict[str, Any]) -> None:
        session = self.store.get_session(session_id)
        if not session:
            raise ValidationError("Session not found", details={"session_id": session_id})
        session.waiting_for_input = True
        session.current_node_id = node_id
        session.pending_input_data = input_data
        session.status = SessionStatus.WAITING_FOR_INPUT
        session.human_input_future = Future()
        session.human_input_value = None
        self.logger.info("Session %s waiting for input at node %s", session_id, node_id)

    def wait_for_human_input(self, session_id: str, timeout: float = 1800.0) -> Any:
        session = self.store.get_session(session_id)
        if not session:
            logger = get_server_logger()
            logger.warning(
                "Session %s not found when waiting for human input", session_id, log_type=LogType.WORKFLOW
            )
            raise ValidationError("Session not found", details={"session_id": session_id})

        future: Optional[Future] = session.human_input_future
        if not session.waiting_for_input or future is None:
            logger = get_server_logger()
            logger.warning(
                "Session %s is not waiting for input", session_id, log_type=LogType.WORKFLOW
            )
            raise ValidationError(
                "Session is not waiting for input",
                details={"session_id": session_id, "waiting_for_input": session.waiting_for_input},
            )

        start_time = time.time()
        poll_interval = 1.0
        try:
            while True:
                if session.cancel_event.is_set():
                    raise WorkflowCancelledError("Workflow execution cancelled", workflow_id=session_id)

                elapsed = time.time() - start_time
                remaining = timeout - elapsed
                if remaining <= 0:
                    raise concurrent.futures.TimeoutError()

                wait_time = min(poll_interval, remaining)
                try:
                    result = future.result(timeout=wait_time)
                    logger = get_server_logger()
                    input_length = 0
                    if isinstance(result, dict):
                        input_length = len(result.get("text") or "")
                    elif result is not None:
                        input_length = len(str(result))
                    logger.info(
                        "Human input received",
                        log_type=LogType.WORKFLOW,
                        session_id=session_id,
                        input_length=input_length,
                    )
                    return result
                except concurrent.futures.TimeoutError:
                    continue
        except concurrent.futures.TimeoutError:
            self.logger.warning("Session %s human input timeout", session_id)
            logger = get_server_logger()
            logger.warning(
                "Human input timeout",
                log_type=LogType.WORKFLOW,
                session_id=session_id,
                timeout_duration=timeout,
            )
            raise CustomTimeoutError("Input timeout", operation="wait_for_human_input", timeout_duration=timeout)
        finally:
            session.waiting_for_input = False
            session.current_node_id = None
            session.pending_input_data = None
            session.human_input_future = None

    def set_waiting_for_approval(self, session_id: str, approval_ids: list[str]) -> None:
        session = self.store.get_session(session_id)
        if not session:
            raise ValidationError("Session not found", details={"session_id": session_id})
        session.waiting_for_approval = True
        session.pending_approval_ids = list(approval_ids)
        session.status = SessionStatus.WAITING_FOR_APPROVAL
        session.approval_future = Future()
        self.logger.info("Session %s waiting for approval on %s", session_id, approval_ids)

    def wait_for_approval(self, session_id: str, timeout: float = 86400.0) -> Any:
        session = self.store.get_session(session_id)
        if not session:
            raise ValidationError("Session not found", details={"session_id": session_id})

        future: Optional[Future] = session.approval_future
        if not session.waiting_for_approval or future is None:
            raise ValidationError(
                "Session is not waiting for approval",
                details={"session_id": session_id, "waiting_for_approval": session.waiting_for_approval},
            )

        start_time = time.time()
        poll_interval = 1.0
        try:
            while True:
                if session.cancel_event.is_set():
                    raise WorkflowCancelledError("Workflow execution cancelled", workflow_id=session_id)

                elapsed = time.time() - start_time
                remaining = timeout - elapsed
                if remaining <= 0:
                    raise concurrent.futures.TimeoutError()

                wait_time = min(poll_interval, remaining)
                try:
                    return future.result(timeout=wait_time)
                except concurrent.futures.TimeoutError:
                    continue
        except concurrent.futures.TimeoutError:
            raise CustomTimeoutError("Approval timeout", operation="wait_for_approval", timeout_duration=timeout)
        finally:
            session.waiting_for_approval = False
            session.pending_approval_ids = []
            session.approval_future = None

    def provide_human_input(self, session_id: str, user_input: Any) -> None:
        session = self.store.get_session(session_id)
        if not session:
            logger = get_server_logger()
            logger.warning("Session %s not found when providing human input", session_id)
            raise ValidationError(
                "Session not found", details={"session_id": session_id, "input_provided": user_input is not None}
            )

        future: Optional[Future] = session.human_input_future
        if not session.waiting_for_input or future is None:
            logger = get_server_logger()
            logger.warning("Session %s is not waiting for input when providing data", session_id)
            raise ValidationError(
                "Session is not waiting for input",
                details={"session_id": session_id, "waiting_for_input": session.waiting_for_input},
            )

        future.set_result(user_input)
        session.waiting_for_input = False
        length = 0
        if isinstance(user_input, dict):
            length = len(user_input.get("text") or "")
        elif user_input is not None:
            length = len(str(user_input))
        logger = get_server_logger()
        logger.info(
            "Human input provided",
            log_type=LogType.WORKFLOW,
            session_id=session_id,
            input_length=length,
        )

    def notify_approval_state(self, session_id: str) -> bool:
        session = self.store.get_session(session_id)
        if not session or not session.waiting_for_approval:
            return False

        approvals = ((session.team_state or {}).get("approvals") or [])
        open_blocking = [
            approval for approval in approvals
            if isinstance(approval, dict)
            and approval.get("blocking")
            and approval.get("status") != "resolved"
        ]

        if open_blocking:
            session.pending_approval_ids = [str(item.get("id") or "") for item in open_blocking if str(item.get("id") or "").strip()]
            return False

        future: Optional[Future] = session.approval_future
        if future and not future.done():
            future.set_result(session.team_state)
        session.waiting_for_approval = False
        session.pending_approval_ids = []
        return True

    def cleanup_session(self, session_id: str) -> None:
        session = self.store.get_session(session_id)
        if not session:
            return
        future: Optional[Future] = session.human_input_future
        if future and not future.done():
            future.cancel()
        promise = session.input_promise
        if promise and not promise.done():
            promise.cancel()
        approval_future: Optional[Future] = session.approval_future
        if approval_future and not approval_future.done():
            approval_future.cancel()
        session.waiting_for_input = False
        session.waiting_for_approval = False
        session.current_node_id = None
        session.pending_input_data = None
        session.human_input_future = None
        session.human_input_value = None
        session.pending_approval_ids = []
        session.approval_future = None
        self.logger.info("Session %s cleaned from execution controller", session_id)
