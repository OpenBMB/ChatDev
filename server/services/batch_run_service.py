"""Batch workflow execution helpers."""

import asyncio
import csv
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from check.check import load_config
from entity.enums import LogLevel
from entity.graph_config import GraphConfig
from utils.exceptions import ValidationError
from utils.task_input import TaskInputBuilder
from workflow.graph import GraphExecutor
from workflow.graph_context import GraphContext

from server.services.batch_parser import BatchTask
from server.services.workflow_storage import validate_workflow_filename
from server.settings import WARE_HOUSE_DIR, YAML_DIR


class BatchRunService:
    """Runs batch workflows and reports progress over WebSocket."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    async def run_batch(
        self,
        session_id: str,
        yaml_file: str,
        tasks: List[BatchTask],
        websocket_manager,
        *,
        max_parallel: int = 5,
        file_base: str = "batch",
        log_level: Optional[LogLevel] = None,
    ) -> None:
        batch_id = session_id
        total = len(tasks)

        await websocket_manager.send_message(
            session_id,
            {"type": "batch_started", "data": {"batch_id": batch_id, "total": total}},
        )

        semaphore = asyncio.Semaphore(max_parallel)
        success_count = 0
        failure_count = 0
        result_rows: List[Dict[str, Any]] = []
        result_lock = asyncio.Lock()

        async def run_task(task: BatchTask) -> None:
            nonlocal success_count, failure_count
            task_id = task.task_id or str(uuid.uuid4())
            task_dir = self._sanitize_label(f"{file_base}-{task_id}")

            await websocket_manager.send_message(
                session_id,
                {
                    "type": "batch_task_started",
                    "data": {
                        "row_index": task.row_index,
                        "task_id": task_id,
                        "task_dir": task_dir,
                    },
                },
            )

            try:
                result = await asyncio.to_thread(
                    self._run_single_task,
                    session_id,
                    yaml_file,
                    task,
                    task_dir,
                    log_level,
                )
                success_count += 1
                async with result_lock:
                    result_rows.append(
                        {
                            "row_index": task.row_index,
                            "task_id": task_id,
                            "task_dir": task_dir,
                            "status": "success",
                            "duration_ms": result["duration_ms"],
                            "token_usage": result["token_usage"],
                            "graph_output": result["graph_output"],
                            "results": result["results"],
                            "error": "",
                        }
                    )
                await websocket_manager.send_message(
                    session_id,
                    {
                        "type": "batch_task_completed",
                        "data": {
                            "row_index": task.row_index,
                            "task_id": task_id,
                            "task_dir": task_dir,
                            "results": result["results"],
                            "token_usage": result["token_usage"],
                            "duration_ms": result["duration_ms"],
                        },
                    },
                )
            except Exception as exc:
                failure_count += 1
                async with result_lock:
                    result_rows.append(
                        {
                            "row_index": task.row_index,
                            "task_id": task_id,
                            "task_dir": task_dir,
                            "status": "failed",
                            "duration_ms": None,
                            "token_usage": None,
                            "graph_output": "",
                            "results": None,
                            "error": str(exc),
                        }
                    )
                await websocket_manager.send_message(
                    session_id,
                    {
                        "type": "batch_task_failed",
                        "data": {
                            "row_index": task.row_index,
                            "task_id": task_id,
                            "task_dir": task_dir,
                            "error": str(exc),
                        },
                    },
                )

        async def run_with_limit(task: BatchTask) -> None:
            async with semaphore:
                await run_task(task)

        await asyncio.gather(*(run_with_limit(task) for task in tasks))

        self._write_batch_outputs(session_id, result_rows)

        await websocket_manager.send_message(
            session_id,
            {
                "type": "batch_completed",
                "data": {
                    "batch_id": batch_id,
                    "total": total,
                    "succeeded": success_count,
                    "failed": failure_count,
                },
            },
        )

    def _write_batch_outputs(self, session_id: str, result_rows: List[Dict[str, Any]]) -> None:
        output_root = WARE_HOUSE_DIR / f"session_{session_id}"
        output_root.mkdir(parents=True, exist_ok=True)

        csv_path = output_root / "batch_results.csv"
        json_path = output_root / "batch_manifest.json"

        fieldnames = [
            "row_index",
            "task_id",
            "task_dir",
            "status",
            "duration_ms",
            "token_usage",
            "results",
            "error",
        ]

        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in result_rows:
                row_copy = dict(row)
                row_copy["token_usage"] = json.dumps(row_copy.get("token_usage"))
                row_copy["results"] = row_copy.get("graph_output", "")
                writer.writerow(row_copy)

        with json_path.open("w", encoding="utf-8") as handle:
            json.dump(result_rows, handle, ensure_ascii=True, indent=2)

    def _run_single_task(
        self,
        session_id: str,
        yaml_file: str,
        task: BatchTask,
        task_dir: str,
        log_level: Optional[LogLevel],
    ) -> Dict[str, Any]:
        yaml_path = self._resolve_yaml_path(yaml_file)
        design = load_config(yaml_path, vars_override=task.vars_override or None)
        if any(node.type == "human" for node in design.graph.nodes):
            raise ValidationError(
                "Batch execution does not support human nodes",
                details={"yaml_file": yaml_file},
            )

        output_root = WARE_HOUSE_DIR / f"session_{session_id}"
        graph_config = GraphConfig.from_definition(
            design.graph,
            name=task_dir,
            output_root=output_root,
            source_path=str(yaml_path),
            vars=design.vars,
        )
        graph_config.metadata["fixed_output_dir"] = True

        if log_level:
            graph_config.log_level = log_level
            graph_config.definition.log_level = log_level

        graph_context = GraphContext(config=graph_config)

        start_time = time.perf_counter()
        executor = GraphExecutor(graph_context, session_id=session_id)
        task_input = self._build_task_input(executor.attachment_store, task)
        executor._execute(task_input)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return {
            "results": executor.outputs,
            "token_usage": executor.token_tracker.get_token_usage(),
            "duration_ms": duration_ms,
            "graph_output": executor.get_final_output(),
        }

    @staticmethod
    def _build_task_input(attachment_store, task: BatchTask):
        if task.attachment_paths:
            builder = TaskInputBuilder(attachment_store)
            return builder.build_from_file_paths(task.task_prompt, task.attachment_paths)
        return task.task_prompt

    @staticmethod
    def _sanitize_label(value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value)
        return cleaned.strip("_") or "task"

    @staticmethod
    def _resolve_yaml_path(yaml_filename: str) -> Path:
        safe_name = validate_workflow_filename(yaml_filename, require_yaml_extension=True)
        yaml_path = YAML_DIR / safe_name
        if not yaml_path.exists():
            raise ValidationError("YAML file not found", details={"yaml_file": safe_name})
        return yaml_path
