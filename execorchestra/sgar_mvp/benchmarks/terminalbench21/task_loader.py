"""Frozen Terminal-Bench 2.1 task loading and identity checks.

The adapter deliberately exposes only instruction and environment metadata to the
method.  ``tests/`` remains outside the task container until verifier time.
"""
from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CANONICAL_BENCHMARK_ID = "terminal-bench/terminal-bench-2-1"
CANONICAL_BENCHMARK_VERSION = "2.1"
CANONICAL_TASK_COUNT = 89
CANONICAL_TASK_TREE_SHA256 = (
    "c31db162da898b59e8f5d827715a65378ca999e4df0dc052fe2a18f4241e0c0b"
)
DEFAULT_TASK_ROOT = Path(
    "benchmarks/terminal-bench-2-1"
)


class TaskPackageError(RuntimeError):
    """Raised when the frozen TB2.1 package is not admissible."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tree_hash(root: Path) -> str:
    # Same identity algorithm as AOrchestra's frozen tb21_manifest.json:
    # sorted ``task-id/relative-path sha256`` lines over all files.
    entries: list[str] = []
    for task_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for path in sorted(p for p in task_dir.rglob("*") if p.is_file()):
            rel = path.relative_to(task_dir).as_posix()
            entries.append(f"{task_dir.name}/{rel} {_sha256_bytes(path.read_bytes())}")
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()


def _safe_task_files(task_dir: Path) -> Iterable[Path]:
    for path in sorted(task_dir.rglob("*")):
        if path.is_symlink():
            raise TaskPackageError(f"task symlink is not allowed: {path}")
        if path.is_file():
            yield path


@dataclass(frozen=True)
class TerminalBenchTask:
    task_id: str
    task_dir: Path
    instruction: str
    config: dict[str, Any]
    task_hash: str
    image: str
    agent_timeout_sec: float
    verifier_timeout_sec: float
    allow_internet: bool
    cpus: int | None
    memory_mb: int | None
    storage_mb: int
    gpus: int

    @property
    def tests_dir(self) -> Path:
        return self.task_dir / "tests"

    @property
    def test_script(self) -> Path:
        return self.tests_dir / "test.sh"


def _number(config: dict[str, Any], key: str, default: float) -> float:
    value = config.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise TaskPackageError(f"invalid numeric task field {key}: {value!r}") from exc


def load_task(task_root: Path, task_id: str) -> TerminalBenchTask:
    task_dir = (task_root / task_id).resolve()
    if not task_dir.is_dir():
        raise TaskPackageError(f"task directory does not exist: {task_dir}")
    task_file = task_dir / "task.toml"
    instruction_file = task_dir / "instruction.md"
    if not task_file.is_file() or not instruction_file.is_file():
        raise TaskPackageError(f"task metadata is incomplete: {task_dir}")
    if not (task_dir / "environment").is_dir() or not (task_dir / "tests").is_dir():
        raise TaskPackageError(f"task environment/tests missing: {task_dir}")
    if not (task_dir / "tests" / "test.sh").is_file():
        raise TaskPackageError(f"official verifier missing: {task_dir / 'tests' / 'test.sh'}")

    config = tomllib.loads(task_file.read_text(encoding="utf-8"))
    environment = dict(config.get("environment") or {})
    agent = dict(config.get("agent") or {})
    verifier = dict(config.get("verifier") or {})
    image = str(environment.get("docker_image") or "").strip()
    if not image or "-vfready" in image:
        raise TaskPackageError(f"invalid formal task image: {image!r}")
    instruction_bytes = instruction_file.read_bytes()
    instruction = instruction_bytes.decode("utf-8", errors="strict")
    task_hash = _tree_hash(task_dir)
    return TerminalBenchTask(
        task_id=task_id,
        task_dir=task_dir,
        instruction=instruction,
        config=config,
        task_hash=task_hash,
        image=image,
        agent_timeout_sec=_number(agent, "timeout_sec", 900.0),
        verifier_timeout_sec=_number(verifier, "timeout_sec", 900.0),
        allow_internet=bool(environment.get("allow_internet", False)),
        cpus=int(_number(environment, "cpus", 0)) if "cpus" in environment else None,
        memory_mb=int(_number(environment, "memory_mb", 0)) if "memory_mb" in environment else None,
        storage_mb=int(_number(environment, "storage_mb", 10240)),
        gpus=int(_number(environment, "gpus", 0)),
    )


def load_tasks(
    task_root: Path = DEFAULT_TASK_ROOT,
    *,
    expected_count: int | None = CANONICAL_TASK_COUNT,
) -> tuple[list[TerminalBenchTask], str]:
    task_root = task_root.resolve()
    if not task_root.is_dir():
        raise TaskPackageError(f"task root does not exist: {task_root}")
    tasks = [
        load_task(task_root, path.name)
        for path in sorted(task_root.iterdir())
        if path.is_dir() and not path.name.startswith(".")
    ]
    if expected_count is not None and len(tasks) != expected_count:
        raise TaskPackageError(
            f"expected {expected_count} tasks, found {len(tasks)} under {task_root}"
        )
    tree_hash = _tree_hash(task_root)
    if expected_count == CANONICAL_TASK_COUNT and tree_hash != CANONICAL_TASK_TREE_SHA256:
        raise TaskPackageError(
            f"canonical TB2.1 tree hash mismatch: expected {CANONICAL_TASK_TREE_SHA256}, got {tree_hash}"
        )
    return tasks, tree_hash


def write_task_manifest(
    path: Path,
    *,
    task: TerminalBenchTask,
    task_tree_sha256: str,
    image_digest: str,
) -> dict[str, Any]:
    payload = {
        "protocol": "sgar-tb21-task-manifest-v1",
        "benchmark_id": CANONICAL_BENCHMARK_ID,
        "benchmark_version": CANONICAL_BENCHMARK_VERSION,
        "task_tree_sha256": task_tree_sha256,
        "task_id": task.task_id,
        "task_hash": task.task_hash,
        "image": task.image,
        "image_digest": image_digest,
        "agent_timeout_sec": task.agent_timeout_sec,
        "verifier_timeout_sec": task.verifier_timeout_sec,
        "allow_internet": task.allow_internet,
        "resources": {
            "cpus": task.cpus,
            "memory_mb": task.memory_mb,
            "storage_mb": task.storage_mb,
            "gpus": task.gpus,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload
