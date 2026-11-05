"""Bind the immutable official dataset to the pre-frozen G2 experiment manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def finalize(pending_path: Path, dataset_path: Path, output_path: Path) -> dict[str, Any]:
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    if dataset.get("task_count") != 165 or dataset.get("immutable") is not True or dataset.get("gold_separated") is not True:
        raise ValueError("gaia_dataset_freeze_gate_invalid")
    result = dict(pending)
    result["status"] = "FROZEN"
    result["dataset"] = {
        "manifest": str(dataset_path.resolve()),
        "manifest_sha256": dataset.get("manifest_sha256"),
        "revision": dataset.get("revision"),
        "task_count": dataset.get("task_count"),
        "level_counts": dataset.get("level_counts"),
        "task_ids_sha256": dataset.get("task_ids_sha256"),
        "raw_tree_sha256": dataset.get("raw_tree_sha256"),
        "gold_separated": True,
        "immutable": True,
    }
    result["freeze_gate"] = {"passed": True, "remaining_item": None}
    result.pop("manifest_sha256", None)
    result["manifest_sha256"] = canonical_sha256(result)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pending", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.pending, args.dataset_manifest, args.output), ensure_ascii=False, indent=2))
