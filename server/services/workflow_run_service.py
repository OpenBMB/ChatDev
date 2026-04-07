"""Service responsible for executing workflows for WebSocket sessions."""

import logging
import asyncio
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from check.check import load_config
from entity.graph_config import GraphConfig
from entity.messages import Message, MessageRole
from entity.enums import LogLevel
from utils.exceptions import ValidationError, WorkflowCancelledError
from utils.structured_logger import get_server_logger, LogType
from utils.task_input import TaskInputBuilder
from workflow.graph_context import GraphContext

from server.services.attachment_service import AttachmentService
from server.services.session_execution import SessionExecutionController
from server.services.session_store import SessionStatus, WorkflowSessionStore
from server.services.team_state_service import TeamStateService
from server.services.websocket_executor import WebSocketGraphExecutor
from server.services.workflow_handoff_service import iter_enabled_handoffs, run_handoff
from server.services.workflow_storage import validate_workflow_filename
from server.settings import WARE_HOUSE_DIR, YAML_DIR


class WorkflowRunService:
    def __init__(
        self,
        session_store: WorkflowSessionStore,
        session_controller: SessionExecutionController,
        attachment_service: AttachmentService,
        team_state_service: TeamStateService | None = None,
    ) -> None:
        self.session_store = session_store
        self.session_controller = session_controller
        self.attachment_service = attachment_service
        self.team_state_service = team_state_service or TeamStateService()
        self.logger = logging.getLogger(__name__)

    def request_cancel(self, session_id: str, *, reason: Optional[str] = None) -> bool:
        session = self.session_store.get_session(session_id)
        if not session:
            return False

        cancel_message = reason or "Cancellation requested"
        session.cancel_reason = cancel_message
        if not session.cancel_event.is_set():
            session.cancel_event.set()
            self.logger.info("Cancellation requested for session %s", session_id)

        if session.executor:
            try:
                session.executor.request_cancel(cancel_message)
            except Exception as exc:
                self.logger.warning("Failed to propagate cancellation to executor for %s: %s", session_id, exc)

        self.session_store.update_session_status(session_id, SessionStatus.CANCELLED, error_message=cancel_message)
        return True

    async def start_workflow(
        self,
        session_id: str,
        yaml_file: str,
        task_prompt: str,
        websocket_manager,
        *,
        attachments: Optional[List[str]] = None,
        variables: Optional[dict] = None,
        team_state: Optional[dict] = None,
        log_level: Optional[LogLevel] = None,
    ) -> None:
        normalized_yaml_name = (yaml_file or "").strip()
        try:
            yaml_path = self._resolve_yaml_path(normalized_yaml_name)
            normalized_yaml_name = yaml_path.name

            attachments = attachments or []
            if (not task_prompt or not task_prompt.strip()) and not attachments:
                raise ValidationError(
                    "Task prompt cannot be empty",
                    details={"task_prompt_provided": bool(task_prompt)},
                )

            self.attachment_service.prepare_session_workspace(session_id)
            self.session_store.create_session(
                yaml_file=normalized_yaml_name,
                task_prompt=task_prompt,
                session_id=session_id,
                attachments=attachments,
                team_state=team_state,
            )
            self.session_store.update_session_status(session_id, SessionStatus.RUNNING)

            await websocket_manager.send_message(
                session_id,
                {
                    "type": "workflow_started",
                    "data": {"yaml_file": normalized_yaml_name, "task_prompt": task_prompt},
                },
            )

            await self._execute_workflow_async(
                session_id,
                yaml_path,
                task_prompt,
                websocket_manager,
                attachments,
                variables,
                team_state,
                log_level,
            )
        except ValidationError as exc:
            self.logger.error(str(exc))
            logger = get_server_logger()
            logger.error(
                "Workflow validation error",
                log_type=LogType.WORKFLOW,
                session_id=session_id,
                yaml_file=normalized_yaml_name,
                validation_details=getattr(exc, "details", None),
            )
            self.session_store.set_session_error(session_id, str(exc))
            await websocket_manager.send_message(
                session_id,
                {"type": "error", "data": {"message": str(exc)}},
            )
        except Exception as exc:
            self.logger.error(f"Error starting workflow for session {session_id}: {exc}")
            logger = get_server_logger()
            logger.log_exception(
                exc,
                "Error starting workflow",
                session_id=session_id,
                yaml_file=normalized_yaml_name,
            )
            self.session_store.set_session_error(session_id, str(exc))
            await websocket_manager.send_message(
                session_id,
                {
                    "type": "error",
                    "data": {"message": f"Failed to start workflow: {exc}"},
                },
            )

    async def _execute_workflow_async(
        self,
        session_id: str,
        yaml_path: Path,
        task_prompt: str,
        websocket_manager,
        attachments: List[str],
        variables: Optional[dict],
        team_state: Optional[dict],
        log_level: LogLevel,
    ) -> None:
        session = self.session_store.get_session(session_id)
        cancel_event = session.cancel_event if session else None
        try:
            effective_team_state = team_state or (session.team_state if session else None)
            replay_context = self._build_replay_context(effective_team_state)

            design = load_config(yaml_path, vars_override=variables)
            design.graph, replay_applied = self._apply_replay_target_to_definition(
                design.graph,
                effective_team_state,
            )
            initialized_team_state = self.team_state_service.initialize_state(
                yaml_file=yaml_path.name,
                task_prompt=task_prompt,
                graph_definition=design.graph,
                existing=effective_team_state,
            )
            initialized_team_state = self._attach_replay_context_to_team_state(
                initialized_team_state,
                replay_context,
            )
            if session:
                session.team_state = initialized_team_state

            await websocket_manager.send_message(
                session_id,
                {
                    "type": "team_state_initialized",
                    "data": {
                        "team_state": initialized_team_state,
                    },
                },
            )
            await websocket_manager.send_message(
                session_id,
                {
                    "type": "plan_created",
                    "data": {
                        "plan": initialized_team_state.get("plan", {}),
                        "team_state": initialized_team_state,
                    },
                },
            )
            await websocket_manager.send_message(
                session_id,
                {
                    "type": "memory_updated",
                    "data": {
                        "memory": initialized_team_state.get("memory", {}),
                        "team_state": initialized_team_state,
                    },
                },
            )
            await self._emit_replay_state(session_id, websocket_manager, initialized_team_state, replay_applied)
            await self._emit_replay_context_state(
                session_id,
                websocket_manager,
                initialized_team_state,
                replay_context,
                replay_applied,
            )

            await self._wait_for_blocking_approvals(session_id, websocket_manager)

            graph_config = GraphConfig.from_definition(
                design.graph,
                name=f"session_{session_id}",
                output_root=WARE_HOUSE_DIR,
                source_path=str(yaml_path),
                vars=design.vars,
            )
            graph_config.metadata["replay_context"] = replay_context
            graph_config.metadata["retained_task_outputs"] = replay_context.get("retained_tasks", [])
            graph_config.metadata["team_state"] = initialized_team_state
            if log_level:
                graph_config.log_level = log_level
                graph_config.definition.log_level = log_level
            graph_context = GraphContext(config=graph_config)

            executor = WebSocketGraphExecutor(
                graph_context,
                session_id,
                self.session_controller,
                self.attachment_service,
                websocket_manager,
                self.session_store,
                cancel_event=cancel_event,
            )

            if session:
                session.graph = graph_context
                session.executor = executor
                if session.cancel_event.is_set():
                    executor.request_cancel(session.cancel_reason or "Cancellation requested")

            task_input = self._build_initial_task_input(
                session_id,
                graph_context,
                task_prompt,
                attachments,
                executor.attachment_store,
                replay_context=replay_context,
            )

            await executor.execute_graph_async(task_input)

            # If cancellation was requested during execution but not raised inside threads,
            # treat the run as cancelled to avoid conflicting status.
            if cancel_event and cancel_event.is_set():
                reason = session.cancel_reason if session else "Cancellation requested"
                raise WorkflowCancelledError(reason, workflow_id=graph_context.name)

            results = executor.get_results()
            summary = graph_context.final_message()
            token_usage = executor.token_tracker.get_token_usage()
            self.session_store.complete_session(session_id, results)

            await websocket_manager.send_message(
                session_id,
                {
                    "type": "workflow_completed",
                    "data": {
                        "results": results,
                        "summary": summary,
                        "token_usage": token_usage,
                    },
                },
            )
            handoff_results = await self._run_handoffs_after_completion(
                session_id,
                websocket_manager,
                handoffs=getattr(design.graph, "handoffs", None),
                source_workflow=yaml_path.name,
                final_message=summary,
                results=results,
                token_usage=token_usage,
                variables=variables,
                log_level=log_level,
            )
            if handoff_results:
                await websocket_manager.send_message(
                    session_id,
                    {
                        "type": "workflow_handoffs_completed",
                        "data": {"handoffs": handoff_results},
                    },
                )

            logger = get_server_logger()
            logger.info(
                "Workflow execution completed successfully",
                log_type=LogType.WORKFLOW,
                session_id=session_id,
                yaml_path=str(yaml_path),
                result_count=len(results) if isinstance(results, dict) else 0,
            )
        except WorkflowCancelledError as exc:
            reason = str(exc)
            session_ref = self.session_store.get_session(session_id)
            if session_ref and session_ref.waiting_for_approval:
                self.session_store.update_session_status(
                    session_id,
                    SessionStatus.WAITING_FOR_APPROVAL,
                    error_message=reason,
                )
            else:
                self.session_store.update_session_status(session_id, SessionStatus.CANCELLED, error_message=reason)
                await websocket_manager.send_message(
                    session_id,
                    {
                        "type": "workflow_cancelled",
                        "data": {"message": reason},
                    },
                )
            logger = get_server_logger()
            logger.info(
                "Workflow execution cancelled" if not (session_ref and session_ref.waiting_for_approval) else "Workflow execution paused for approval",
                log_type=LogType.WORKFLOW,
                session_id=session_id,
                yaml_path=str(yaml_path),
                cancellation_reason=reason,
            )
        except ValidationError as exc:
            self.session_store.set_session_error(session_id, str(exc))
            await websocket_manager.send_message(
                session_id,
                {"type": "error", "data": {"message": str(exc)}},
            )
            logger = get_server_logger()
            logger.error(
                "Workflow validation error",
                log_type=LogType.WORKFLOW,
                session_id=session_id,
                yaml_path=str(yaml_path),
                validation_details=getattr(exc, "details", None),
            )
        except Exception as exc:
            self.session_store.set_session_error(session_id, str(exc))
            await websocket_manager.send_message(
                session_id,
                {"type": "error", "data": {"message": f"Workflow execution error: {exc}"}},
            )
            logger = get_server_logger()
            logger.log_exception(
                exc,
                f"Error executing workflow for session {session_id}",
                session_id=session_id,
                yaml_path=str(yaml_path),
            )
        finally:
            session_ref = self.session_store.get_session(session_id)
            if session_ref:
                session_ref.executor = None
                session_ref.graph = None
            self.session_controller.cleanup_session(session_id)
            if session_id not in websocket_manager.active_connections:
                self.session_store.pop_session(session_id)

    async def _run_handoffs_after_completion(
        self,
        session_id: str,
        websocket_manager,
        *,
        handoffs: Optional[List[Dict[str, Any]]],
        source_workflow: str,
        final_message: str,
        results: Any,
        token_usage: Any,
        variables: Optional[dict],
        log_level: Optional[LogLevel],
    ) -> List[Dict[str, Any]]:
        handoff_results: List[Dict[str, Any]] = []
        for handoff in iter_enabled_handoffs(handoffs):
            await websocket_manager.send_message(
                session_id,
                {
                    "type": "workflow_handoff_started",
                    "data": {
                        "handoff": {
                            "id": handoff["id"],
                            "source_workflow": source_workflow,
                            "target_workflow": handoff["target_workflow"],
                            "input_from": handoff["input_from"],
                        },
                    },
                },
            )
            try:
                handoff_result = await asyncio.to_thread(
                    run_handoff,
                    handoff,
                    source_workflow=source_workflow,
                    final_message=final_message,
                    results=results,
                    token_usage=token_usage,
                    variables=variables,
                    log_level=log_level,
                )
            except Exception as exc:
                handoff_result = {
                    "id": handoff["id"],
                    "status": "failed",
                    "source_workflow": source_workflow,
                    "target_workflow": handoff["target_workflow"],
                    "input_from": handoff["input_from"],
                    "message": str(exc),
                }
                await websocket_manager.send_message(
                    session_id,
                    {
                        "type": "workflow_handoff_failed",
                        "data": {"handoff": handoff_result},
                    },
                )
            else:
                await websocket_manager.send_message(
                    session_id,
                    {
                        "type": "workflow_handoff_completed",
                        "data": {"handoff": handoff_result},
                    },
                )
            handoff_results.append(handoff_result)
        return handoff_results

    def _build_initial_task_input(
        self,
        session_id: str,
        graph_context: GraphContext,
        prompt: str,
        attachment_ids: List[str],
        store,
        *,
        replay_context: Optional[Dict[str, Any]] = None,
    ) -> Union[List[Message], str]:
        replay_message = self._build_replay_context_message(replay_context)

        if not attachment_ids and replay_message is None:
            return prompt

        messages: List[Message] = []
        if replay_message is not None:
            messages.append(replay_message)

        blocks = []
        if attachment_ids:
            blocks = self.attachment_service.build_attachment_blocks(
                session_id,
                attachment_ids,
                target_store=store,
            )

        if blocks:
            messages.extend(TaskInputBuilder(store).build_from_blocks(prompt, blocks))
        elif prompt or not messages:
            messages.append(
                Message(
                    role=MessageRole.USER,
                    content=prompt or "",
                    metadata={"source": "TASK"},
                )
            )

        return messages

    def _resolve_yaml_path(self, yaml_filename: str) -> Path:
        """Validate and resolve YAML paths inside the configured directory."""

        safe_name = validate_workflow_filename(yaml_filename, require_yaml_extension=True)
        yaml_path = YAML_DIR / safe_name
        if not yaml_path.exists():
            raise ValidationError("YAML file not found", details={"yaml_file": safe_name})
        return yaml_path

    def _apply_replay_target_to_definition(self, graph_definition, team_state: Optional[dict]):
        replay = ((team_state or {}).get("replay") or {})
        target_task_id = str(replay.get("target_task_id") or "").strip()
        if not target_task_id:
            return graph_definition, False

        definition = deepcopy(graph_definition)
        node_ids = {
            str(getattr(node, "id", "") or "").strip()
            for node in getattr(definition, "nodes", []) or []
        }
        if target_task_id not in node_ids:
            return definition, False

        definition.start_nodes = [target_task_id]
        return definition, True

    def _attach_replay_context_to_team_state(
        self,
        team_state: Optional[dict],
        replay_context: Optional[Dict[str, Any]],
    ) -> dict:
        payload = deepcopy(team_state or self.team_state_service.empty_state())
        artifacts = dict((payload.get("artifacts") or {}))
        artifacts["replay_context"] = {
            "target_task_id": str((replay_context or {}).get("target_task_id") or "").strip(),
            "target_task_title": str((replay_context or {}).get("target_task_title") or "").strip(),
            "retained_tasks": list((replay_context or {}).get("retained_tasks") or []),
            "retained_node_ids": list((replay_context or {}).get("retained_node_ids") or []),
            "text": str((replay_context or {}).get("text") or "").strip(),
        }
        payload["artifacts"] = artifacts
        return self.team_state_service.merge_state(None, payload)

    def _build_replay_context(self, team_state: Optional[dict]) -> Dict[str, Any]:
        replay = ((team_state or {}).get("replay") or {})
        target_task_id = str(replay.get("target_task_id") or "").strip()
        target_task_title = str(replay.get("target_task_title") or "").strip()
        if not target_task_id:
            return {
                "target_task_id": "",
                "target_task_title": "",
                "retained_tasks": [],
                "retained_node_ids": [],
                "text": "",
            }

        tasks = ((team_state or {}).get("plan") or {}).get("tasks") or []
        if not isinstance(tasks, list):
            tasks = []

        target_index = -1
        for index, task in enumerate(tasks):
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("id") or task.get("node_id") or "").strip()
            if task_id == target_task_id:
                target_index = index
                if not target_task_title:
                    target_task_title = str(task.get("title") or "").strip()
                break

        if target_index <= 0:
            return {
                "target_task_id": target_task_id,
                "target_task_title": target_task_title,
                "retained_tasks": [],
                "retained_node_ids": [],
                "text": "",
            }

        task_outputs = (((team_state or {}).get("artifacts") or {}).get("task_outputs") or {})
        retained_tasks: List[Dict[str, str]] = []
        for task in tasks[:target_index]:
            if not isinstance(task, dict):
                continue
            if str(task.get("status") or "").strip() != "done":
                continue
            task_id = str(task.get("id") or task.get("node_id") or "").strip()
            if not task_id:
                continue
            artifact = task_outputs.get(task_id) if isinstance(task_outputs, dict) else {}
            preview = str(
                task.get("output_preview")
                or (artifact or {}).get("output_preview")
                or ""
            ).strip()
            output_text = str((artifact or {}).get("output_text") or "").strip()
            if not preview and not output_text:
                continue
            retained_tasks.append(
                {
                    "task_id": task_id,
                    "node_id": str((artifact or {}).get("node_id") or task.get("node_id") or task_id).strip(),
                    "title": str(task.get("title") or task_id).strip(),
                    "preview": " ".join(preview.split()),
                    "output_text": output_text,
                }
            )

        if not retained_tasks:
            return {
                "target_task_id": target_task_id,
                "target_task_title": target_task_title,
                "retained_tasks": [],
                "retained_node_ids": [],
                "text": "",
            }

        lines = [
            "[Replay Context]",
            "The tasks below were completed in an earlier approved pass. Reuse them as confirmed context unless new evidence explicitly invalidates them.",
        ]
        if target_task_title or target_task_id:
            lines.append(f"Replay target: {target_task_title or target_task_id}")
        lines.append("Retained outputs:")
        for item in retained_tasks:
            lines.append(f"- {item['title']}: {item['preview']}")

        return {
            "target_task_id": target_task_id,
            "target_task_title": target_task_title,
            "retained_tasks": retained_tasks,
            "retained_node_ids": [
                str(item.get("node_id") or item.get("task_id") or "").strip()
                for item in retained_tasks
                if str(item.get("node_id") or item.get("task_id") or "").strip()
            ],
            "text": "\n".join(lines).strip(),
        }

    def _build_replay_context_message(self, replay_context: Optional[Dict[str, Any]]) -> Message | None:
        context_text = str((replay_context or {}).get("text") or "").strip()
        retained_tasks = list((replay_context or {}).get("retained_tasks") or [])
        if not context_text and not retained_tasks:
            return None

        return Message(
            role=MessageRole.SYSTEM,
            content=context_text or "Replay context is attached for this run.",
            metadata={
                "source": "REPLAY_CONTEXT",
                "replay_context": replay_context or {},
                "retained_task_outputs": retained_tasks,
            },
            preserve_role=True,
            keep=True,
        )

    async def _emit_replay_state(
        self,
        session_id: str,
        websocket_manager,
        team_state: Optional[dict],
        replay_applied: bool,
    ) -> None:
        replay = ((team_state or {}).get("replay") or {})
        target_task_id = str(replay.get("target_task_id") or "").strip()
        if not target_task_id:
            return

        await websocket_manager.send_message(
            session_id,
            {
                "type": "replay_applied" if replay_applied else "replay_ignored",
                "data": {
                    "replay": replay,
                    "team_state": team_state,
                },
            },
        )

    async def _emit_replay_context_state(
        self,
        session_id: str,
        websocket_manager,
        team_state: Optional[dict],
        replay_context: Optional[Dict[str, Any]],
        replay_applied: bool,
    ) -> None:
        retained_tasks = (replay_context or {}).get("retained_tasks") or []
        if not replay_applied or not retained_tasks:
            return

        await websocket_manager.send_message(
            session_id,
            {
                "type": "replay_context_attached",
                "data": {
                    "replay": (team_state or {}).get("replay", {}),
                    "replay_context": replay_context,
                    "team_state": team_state,
                },
            },
        )

    def get_team_state(self, session_id: str) -> Optional[dict]:
        session = self.session_store.get_session(session_id)
        if not session:
            return None
        return session.team_state or self.team_state_service.empty_state()

    async def update_team_state(
        self,
        session_id: str,
        incoming_state: Optional[dict],
        websocket_manager,
    ) -> Optional[dict]:
        session = self.session_store.get_session(session_id)
        if not session:
            return None

        previous_state = session.team_state or self.team_state_service.empty_state()
        next_state = self.team_state_service.merge_state(previous_state, incoming_state)
        session.team_state = next_state
        approval_resolved = self.session_controller.notify_approval_state(session_id)

        for event in self.team_state_service.build_update_events(previous_state, next_state):
            await websocket_manager.send_message(session_id, event)

        if approval_resolved:
            if session.executor is not None and not session.cancel_event.is_set():
                self.session_store.update_session_status(session_id, SessionStatus.RUNNING)
                await websocket_manager.send_message(
                    session_id,
                    {
                        "type": "approval_gate_resumed",
                        "data": {
                            "team_state": next_state,
                        },
                    },
                )
            else:
                self.session_store.update_session_status(session_id, SessionStatus.IDLE)
                replay = next_state.get("replay", {}) or {}
                event_type = "review_replay_ready" if replay.get("target_task_id") else "review_replay_dismissed"
                await websocket_manager.send_message(
                    session_id,
                    {
                        "type": event_type,
                        "data": {
                            "team_state": next_state,
                            "replay": replay,
                        },
                    },
                )

        return next_state

    async def _wait_for_blocking_approvals(self, session_id: str, websocket_manager) -> None:
        session = self.session_store.get_session(session_id)
        if not session:
            return

        approvals = ((session.team_state or {}).get("approvals") or [])
        blocking_open = [
            approval for approval in approvals
            if isinstance(approval, dict)
            and approval.get("blocking")
            and approval.get("status") != "resolved"
        ]
        if not blocking_open:
            return

        approval_ids = [str(item.get("id") or "") for item in blocking_open if str(item.get("id") or "").strip()]
        self.session_controller.set_waiting_for_approval(session_id, approval_ids)
        self.session_store.update_session_status(session_id, SessionStatus.WAITING_FOR_APPROVAL)

        await websocket_manager.send_message(
            session_id,
            {
                "type": "approval_gate_waiting",
                "data": {
                    "approvals": blocking_open,
                    "team_state": session.team_state,
                },
            },
        )

        for approval in blocking_open:
            await websocket_manager.send_message(
                session_id,
                {
                    "type": "approval_required",
                    "data": {
                        "approval": approval,
                        "team_state": session.team_state,
                    },
                },
            )

        await asyncio.get_running_loop().run_in_executor(
            None,
            self.session_controller.wait_for_approval,
            session_id,
        )
