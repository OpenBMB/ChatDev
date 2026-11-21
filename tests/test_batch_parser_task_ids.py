"""Batch uploads must keep identifier cells exactly as written.

``parse_batch_file`` feeds the uploaded table to pandas, so dtype inference on
an ``id`` column rewrites identifiers before the runner sees them. These cases
cover the two user-visible shapes: an empty id cell (float64 column, "1.0") and
zero-padded ids ("001" -> "1").
"""

import csv
import io
import json

import pytest

from server.services.batch_parser import parse_batch_file
from utils.exceptions import ValidationError


def test_csv_task_ids_are_preserved_with_blank_cell():
    payload = b"id,task\n1,first task\n,second task\n"

    tasks, file_base = parse_batch_file(payload, "orders.csv")

    assert file_base == "orders"
    assert [task.task_id for task in tasks] == ["1", None]
    assert [task.task_prompt for task in tasks] == ["first task", "second task"]


def test_csv_task_ids_keep_leading_zeros():
    payload = b"id,task\n001,first task\n002,second task\n"

    tasks, _ = parse_batch_file(payload, "orders.csv")

    assert [task.task_id for task in tasks] == ["001", "002"]


def test_csv_json_columns_still_parse():
    vars_payload = json.dumps({"locale": "zh", "retries": 2})
    attachments_payload = json.dumps(["inputs/a.txt"])
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "task", "attachments", "vars"])
    writer.writerow(["7", "write the report", attachments_payload, vars_payload])

    tasks, _ = parse_batch_file(buffer.getvalue().encode("utf-8"), "orders.csv")

    assert tasks[0].task_id == "7"
    assert tasks[0].attachment_paths == ["inputs/a.txt"]
    assert tasks[0].vars_override == {"locale": "zh", "retries": 2}


def test_duplicate_numeric_ids_are_still_rejected():
    payload = b"id,task\n1,first task\n1,second task\n"

    with pytest.raises(ValidationError):
        parse_batch_file(payload, "orders.csv")
