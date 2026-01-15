"""Parse batch task files (CSV/Excel) into runnable tasks."""

import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from utils.exceptions import ValidationError


@dataclass(frozen=True)
class BatchTask:
    row_index: int
    task_id: Optional[str]
    task_prompt: str
    attachment_paths: List[str]
    vars_override: Dict[str, Any]


def parse_batch_file(content: bytes, filename: str) -> Tuple[List[BatchTask], str]:
    """Parse a CSV/Excel batch file and return tasks plus file base name."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise ValidationError("Unsupported file type; must be .csv or .xlsx/.xls", field="file")

    if suffix == ".csv":
        df = _read_csv(content)
    else:
        df = _read_excel(content)

    file_base = Path(filename).stem or "batch"
    tasks = _parse_dataframe(df)
    if not tasks:
        raise ValidationError("Batch file contains no tasks", field="file")
    return tasks, file_base


def _read_csv(content: bytes) -> pd.DataFrame:
    try:
        import chardet
    except Exception:
        chardet = None
    encoding = "utf-8"
    if chardet:
        detected = chardet.detect(content)
        encoding = detected.get("encoding") or encoding
    try:
        return pd.read_csv(BytesIO(content), encoding=encoding)
    except Exception as exc:
        raise ValidationError(f"Failed to read CSV: {exc}", field="file")


def _read_excel(content: bytes) -> pd.DataFrame:
    try:
        return pd.read_excel(BytesIO(content))
    except Exception as exc:
        raise ValidationError(f"Failed to read Excel file: {exc}", field="file")


def _parse_dataframe(df: pd.DataFrame) -> List[BatchTask]:
    column_map = {str(col).strip().lower(): col for col in df.columns}
    id_col = column_map.get("id")
    task_col = column_map.get("task")
    attachments_col = column_map.get("attachments")
    vars_col = column_map.get("vars")

    tasks: List[BatchTask] = []
    seen_ids: set[str] = set()

    for row_index, row in enumerate(df.to_dict(orient="records"), start=1):
        task_prompt = _get_cell_text(row, task_col)
        attachment_paths = _parse_json_list(row, attachments_col, row_index)
        vars_override = _parse_json_dict(row, vars_col, row_index)

        if not task_prompt and not attachment_paths:
            raise ValidationError(
                "Task and attachments cannot both be empty",
                details={"row_index": row_index},
            )

        task_id = _get_cell_text(row, id_col)
        if task_id:
            if task_id in seen_ids:
                raise ValidationError(
                    "Duplicate ID in batch file",
                    details={"row_index": row_index, "task_id": task_id},
                )
            seen_ids.add(task_id)

        tasks.append(
            BatchTask(
                row_index=row_index,
                task_id=task_id or None,
                task_prompt=task_prompt,
                attachment_paths=attachment_paths,
                vars_override=vars_override,
            )
        )
    return tasks


def _get_cell_text(row: Dict[str, Any], column: Optional[str]) -> str:
    if not column:
        return ""
    value = row.get(column)
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _parse_json_list(
    row: Dict[str, Any],
    column: Optional[str],
    row_index: int,
) -> List[str]:
    if not column:
        return []
    raw_value = row.get(column)
    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
        return []
    if isinstance(raw_value, list):
        return _ensure_string_list(raw_value, row_index, "Attachments")
    if isinstance(raw_value, str):
        if not raw_value.strip():
            return []
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                f"Invalid JSON in Attachments: {exc}",
                details={"row_index": row_index},
            )
        return _ensure_string_list(parsed, row_index, "Attachments")
    raise ValidationError(
        "Attachments must be a JSON list",
        details={"row_index": row_index},
    )


def _parse_json_dict(
    row: Dict[str, Any],
    column: Optional[str],
    row_index: int,
) -> Dict[str, Any]:
    if not column:
        return {}
    raw_value = row.get(column)
    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
        return {}
    if isinstance(raw_value, dict):
        return raw_value
    if isinstance(raw_value, str):
        if not raw_value.strip():
            return {}
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                f"Invalid JSON in Vars: {exc}",
                details={"row_index": row_index},
            )
        if not isinstance(parsed, dict):
            raise ValidationError(
                "Vars must be a JSON object",
                details={"row_index": row_index},
            )
        return parsed
    raise ValidationError(
        "Vars must be a JSON object",
        details={"row_index": row_index},
    )


def _ensure_string_list(value: Any, row_index: int, field: str) -> List[str]:
    if not isinstance(value, list):
        raise ValidationError(
            f"{field} must be a JSON list",
            details={"row_index": row_index},
        )
    result: List[str] = []
    for item in value:
        if item is None or (isinstance(item, float) and pd.isna(item)):
            continue
        result.append(str(item))
    return result
