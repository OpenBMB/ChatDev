"""Freeze an official GAIA validation snapshot into private gold-separated storage."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any


PROTOCOL = "gaia-official-dataset-snapshot-v1"
GOLD_KEYS = {"final answer", "final_answer", "expected_answer", "answer", "gold"}


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_validation_root(source: Path) -> Path:
    source = source.resolve()
    candidates = (source, source / "2023/validation", source / "Gaia/2023/validation")
    return next(
        (
            path
            for path in candidates
            if (path / "metadata.jsonl").is_file() or (path / "metadata.parquet").is_file()
        ),
        source,
    )


def _load_metadata(validation: Path) -> tuple[Path, list[dict[str, Any]]]:
    jsonl = validation / "metadata.jsonl"
    if jsonl.is_file():
        return jsonl, [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    parquet = validation / "metadata.parquet"
    if parquet.is_file():
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError("gaia_parquet_requires_pyarrow") from exc
        return parquet, pq.read_table(parquet).to_pylist()
    raise ValueError("gaia_validation_metadata_missing")


def freeze_dataset(source: Path, output: Path, *, revision: str, expected_count: int = 165) -> dict[str, Any]:
    validation = _resolve_validation_root(source)
    metadata, rows = _load_metadata(validation)
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("gaia_dataset_snapshot_destination_not_empty")
    if len(rows) != expected_count:
        raise ValueError(f"gaia_validation_task_count_mismatch:{len(rows)}")

    task_ids: list[str] = []
    levels: dict[str, int] = {}
    visible_rows: list[dict[str, Any]] = []
    evaluator_rows: list[dict[str, Any]] = []
    attachment_names: set[str] = set()
    for row in rows:
        task_id = str(row.get("task_id") or row.get("id") or "").strip()
        question = str(row.get("Question") or row.get("question") or "").strip()
        if not task_id or not question or "Final answer" not in row:
            raise ValueError("gaia_validation_row_schema_invalid")
        if task_id in task_ids:
            raise ValueError("gaia_validation_task_id_duplicate")
        task_ids.append(task_id)
        level_raw = row.get("Level") if row.get("Level") is not None else row.get("level")
        level = str(level_raw).strip().upper().removeprefix("LEVEL ").removeprefix("L")
        if level not in {"1", "2", "3"}:
            raise ValueError("gaia_validation_level_invalid")
        levels[level] = levels.get(level, 0) + 1
        raw_file = row.get("file_name") or row.get("file_path") or ""
        names = [raw_file] if isinstance(raw_file, str) else list(raw_file or [])
        names = [str(name).strip() for name in names if str(name).strip()]
        for name in names:
            relative_name = name.removeprefix("2023/validation/")
            candidate = (validation / relative_name).resolve()
            if validation.resolve() not in candidate.parents or not candidate.is_file():
                raise ValueError("gaia_validation_attachment_missing_or_outside_root")
            attachment_names.add(name)
        visible = {
            "task_id": task_id,
            "Question": question,
            "Level": int(level),
            "file_name": names[0] if len(names) == 1 else names,
            "split": "2023_validation",
        }
        if any(key.casefold() in GOLD_KEYS for key in visible):
            raise AssertionError("gaia_visible_snapshot_gold_key")
        visible_rows.append(visible)
        evaluator_rows.append({"task_id": task_id, "Final answer": row["Final answer"], "split": "2023_validation"})

    raw_root = output / "raw/2023/validation"
    shutil.copytree(validation, raw_root, symlinks=False)
    views = output / "views"
    views.mkdir(parents=True)
    visible_path = views / "agent_visible.jsonl"
    evaluator_path = views / "evaluator_only.jsonl"
    visible_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in visible_rows), encoding="utf-8")
    evaluator_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in evaluator_rows), encoding="utf-8")

    raw_files = sorted(path for path in raw_root.rglob("*") if path.is_file())
    files = {path.relative_to(output).as_posix(): _file_sha256(path) for path in raw_files}
    attachment_hashes = {
        name: _file_sha256(raw_root / name.removeprefix("2023/validation/"))
        for name in sorted(attachment_names)
    }
    manifest = {
        "protocol": PROTOCOL,
        "source": "gaia-benchmark/GAIA",
        "revision": revision,
        "split": "2023_validation",
        "task_count": len(rows),
        "level_counts": {"L1": levels.get("1", 0), "L2": levels.get("2", 0), "L3": levels.get("3", 0)},
        "task_ids": task_ids,
        "task_ids_sha256": _canonical_sha256(task_ids),
        "metadata_file": metadata.name,
        "metadata_sha256": _file_sha256(raw_root / metadata.name),
        "attachment_count": len(attachment_hashes),
        "attachment_hashes": attachment_hashes,
        "raw_files_sha256": files,
        "raw_tree_sha256": _canonical_sha256(files),
        "agent_visible_sha256": _file_sha256(visible_path),
        "evaluator_only_sha256": _file_sha256(evaluator_path),
        "gold_separated": True,
        "immutable": True,
    }
    manifest["manifest_sha256"] = _canonical_sha256(manifest)
    manifest_path = output / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for path in raw_files:
        os.chmod(path, 0o440)
    for path in sorted((path for path in raw_root.rglob("*") if path.is_dir()), reverse=True):
        os.chmod(path, 0o550)
    os.chmod(raw_root, 0o550)
    os.chmod(evaluator_path, 0o400)
    os.chmod(visible_path, 0o440)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--expected-count", type=int, default=165)
    args = parser.parse_args()
    print(json.dumps(freeze_dataset(args.source, args.output, revision=args.revision, expected_count=args.expected_count), ensure_ascii=False, indent=2))
