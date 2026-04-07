import asyncio
from typing import Any, Dict

from entity.enums import LogLevel, EventType
from server.services.team_state_service import TeamStateService
from utils.logger import WorkflowLogger, LogEntry
from utils.structured_logger import get_workflow_logger


class WebSocketLogger(WorkflowLogger):
    """Workflow logger that also pushes entries via WebSocket."""

    def __init__(
        self,
        websocket_manager,
        session_id: str,
        workflow_id: str = None,
        log_level: LogLevel = LogLevel.DEBUG,
        session_store=None,
        session_controller=None,
        team_state_service: TeamStateService | None = None,
    ):
        super().__init__(workflow_id, log_level, log_to_console=False)
        self.websocket_manager = websocket_manager
        self.session_id = session_id
        self.session_store = session_store
        self.session_controller = session_controller
        self.team_state_service = team_state_service or TeamStateService()

    @staticmethod
    def _build_output_preview(log_entry: LogEntry) -> str:
        details = log_entry.details or {}
        output = details.get("output")
        if output is None:
            return ""
        text = str(output or "").strip()
        if not text:
            return ""
        compact = " ".join(text.split())
        if len(compact) <= 240:
            return compact
        return f"{compact[:239].rstrip()}..."

    def add_log(self, level: LogLevel, message: str = None, node_id: str = None,
                event_type: EventType = None, details: Dict[str, Any] = None,
                duration: float = None) -> LogEntry | None:
        log_entry = super().add_log(level, message, node_id, event_type, details, duration)
        if not log_entry:
            return None

        # Send the message using the sync method which handles event loop properly
        self.websocket_manager.send_message_sync(self.session_id, {
            "type": "log",
            "data": log_entry.to_dict()
        })

        self._sync_task_state(log_entry)
        
        return log_entry

    def _sync_task_state(self, log_entry: LogEntry) -> None:
        if not self.session_store or log_entry.level != LogLevel.INFO:
            return

        if log_entry.event_type not in {EventType.NODE_START, EventType.NODE_END}:
            return

        session = self.session_store.get_session(self.session_id)
        if not session:
            return

        node_id = str(log_entry.node_id or "").strip()
        if not node_id:
            return

        next_status = "running" if log_entry.event_type == EventType.NODE_START else "done"
        output_preview = None
        output_text = None
        output_size = None
        reused_replay_output = False
        replay_injected_predecessors = []
        details = log_entry.details or {}
        if log_entry.event_type == EventType.NODE_START:
            replay_injected_predecessors = [
                str(value or "").strip()
                for value in (details.get("replay_injected_predecessors") or [])
                if str(value or "").strip()
            ]
        if log_entry.event_type == EventType.NODE_END:
            output_preview = self._build_output_preview(log_entry)
            output_text = details.get("output")
            output_size = details.get("output_size")
            reused_replay_output = bool(details.get("reused_replay_output", False))
        next_state, task = self.team_state_service.update_task_status_for_node(
            session.team_state,
            node_id=node_id,
            status=next_status,
            output_preview=output_preview,
            output_text=output_text,
            output_size=output_size,
            reused_replay_output=reused_replay_output,
            replay_injected_predecessors=replay_injected_predecessors,
        )

        review_events = []
        if log_entry.event_type == EventType.NODE_END:
            details = log_entry.details or {}
            reviewed_state, review = self.team_state_service.apply_review_directive(
                next_state,
                reviewer_node_id=node_id,
                output_text=details.get("output"),
            )
            if review:
                review_events = [
                    event
                    for event in self.team_state_service.build_update_events(next_state, reviewed_state)
                    if event.get("type") in {"review_replay_suggested", "replay_requested", "approval_required"}
                ]
                next_state = reviewed_state

        session.team_state = next_state

        self.websocket_manager.send_message_sync(
            self.session_id,
            {
                "type": "task_status_changed",
                "data": {
                    "task": task,
                    "team_state": next_state,
                },
            },
        )

        if reused_replay_output and task:
            self.websocket_manager.send_message_sync(
                self.session_id,
                {
                    "type": "task_reused",
                    "data": {
                        "task": task,
                        "team_state": next_state,
                    },
                },
            )

        if replay_injected_predecessors and task:
            self.websocket_manager.send_message_sync(
                self.session_id,
                {
                    "type": "task_dependencies_injected",
                    "data": {
                        "task": task,
                        "team_state": next_state,
                        "predecessors": replay_injected_predecessors,
                    },
                },
            )

        for event in review_events:
            self.websocket_manager.send_message_sync(self.session_id, event)

        if review_events:
            self._pause_execution_for_review(next_state)

    def _pause_execution_for_review(self, next_state: Dict[str, Any]) -> None:
        session = self.session_store.get_session(self.session_id) if self.session_store else None
        if not session or session.waiting_for_approval:
            return

        approvals = ((next_state or {}).get("approvals") or [])
        blocking_open = [
            approval for approval in approvals
            if isinstance(approval, dict)
            and approval.get("blocking")
            and approval.get("status") != "resolved"
        ]
        approval_ids = [str(item.get("id") or "").strip() for item in blocking_open if str(item.get("id") or "").strip()]
        if not approval_ids or not self.session_controller:
            return

        self.session_controller.set_waiting_for_approval(self.session_id, approval_ids)
        self.websocket_manager.send_message_sync(
            self.session_id,
            {
                "type": "approval_gate_waiting",
                "data": {
                    "approvals": blocking_open,
                    "team_state": next_state,
                },
            },
        )
        self.websocket_manager.send_message_sync(
            self.session_id,
            {
                "type": "review_execution_paused",
                "data": {
                    "approvals": blocking_open,
                    "team_state": next_state,
                },
            },
        )

        pause_reason = "Paused for review replay approval"
        session.cancel_reason = pause_reason
        if not session.cancel_event.is_set():
            session.cancel_event.set()
        if session.executor:
            try:
                session.executor.request_cancel(pause_reason)
            except Exception:
                pass
