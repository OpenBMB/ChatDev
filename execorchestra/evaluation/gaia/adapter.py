"""Task/evaluator adapter for GAIA, deliberately separate from SGAR routing."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .answer import GaiaAnswer, extract_model_answer
from .scorer import score_answer


@dataclass(frozen=True)
class AgentVisibleTask:
    task_id: str
    question: str
    level: int | None
    attachments: tuple[str, ...] = ()
    split: str = "synthetic"


@dataclass(frozen=True)
class EvaluatorRecord:
    task_id: str
    final_answer: Any
    expected_answer: Any
    split: str


class GaiaTaskAdapter:
    """Load rows while making evaluator-only fields structurally inaccessible."""

    protocol = "sgar-gaia-task-adapter-v1"

    def __init__(self, *, dataset_root: str | Path, split: str = "synthetic"):
        self.dataset_root = Path(dataset_root).resolve()
        self.split = split

    def load_row(self, row: Mapping[str, Any]) -> tuple[AgentVisibleTask, EvaluatorRecord]:
        task_id = str(row.get("task_id") or row.get("id") or "").strip()
        if not task_id:
            raise ValueError("gaia_task_id_missing")
        question = str(row.get("Question") or row.get("question") or "").strip()
        if not question:
            raise ValueError("gaia_question_missing")
        raw_attachments = row.get("file_name") or row.get("attachments") or ()
        if isinstance(raw_attachments, str):
            raw_attachments = (raw_attachments,)
        attachments = tuple(str(item) for item in raw_attachments if str(item))
        level = row.get("Level") if row.get("Level") is not None else row.get("level")
        level = int(level) if level is not None else None
        visible = AgentVisibleTask(task_id, question, level, attachments, self.split)
        expected_answer = row.get(
            "Final answer",
            row.get("final_answer", row.get("expected_answer")),
        )
        evaluator = EvaluatorRecord(task_id, None, expected_answer, self.split)
        return visible, evaluator

    def visible_context(self, task: AgentVisibleTask) -> dict[str, Any]:
        payload = {
            "task_id": task.task_id,
            "question": task.question,
            "level": task.level,
            "attachments": list(task.attachments),
            "split": task.split,
        }
        if any("answer" in key.casefold() for key in payload):
            raise AssertionError("gaia_answer_leakage")
        return payload

    def evaluate(self, task: AgentVisibleTask, evaluator: EvaluatorRecord, final_output: Any) -> dict[str, Any]:
        if task.task_id != evaluator.task_id:
            raise ValueError("gaia_task_evaluator_identity_mismatch")
        answer: GaiaAnswer = extract_model_answer(final_output)
        result = score_answer(answer.model_answer, evaluator.expected_answer)
        return {
            "protocol": "sgar-gaia-evaluation-v1",
            "task_id": task.task_id,
            "split": task.split,
            "answer": {"model_answer": answer.model_answer, "status": answer.status, "extraction": answer.extraction},
            "scorer": result,
        }

    def attachment_path(self, task: AgentVisibleTask, name: str) -> Path:
        if name not in task.attachments:
            raise ValueError("gaia_attachment_not_declared")
        path = (self.dataset_root / name).resolve()
        if self.dataset_root not in path.parents or not path.is_file():
            raise ValueError("gaia_attachment_missing_or_outside_dataset")
        return path


def row_without_gold(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return a defensive visible projection, useful for leakage tests."""
    return {
        key: value for key, value in row.items()
        if key.casefold() not in {"final answer", "final_answer", "expected_answer", "answer", "gold"}
    }
