"""End-to-end native SGAR runner for one frozen TB2.1 task."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import posixpath
import re
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from sgar_mvp.scripts.external_substrate_worker import (
    DEFAULT_MAX_EMBEDDING_REQUESTS,
)
from sgar_mvp.src.model_media import is_model_media_path, MAX_MODEL_MEDIA_BYTES

from .docker_runtime import DockerTaskRuntime, TaskRuntimeError
from .task_loader import (
    CANONICAL_BENCHMARK_ID,
    CANONICAL_BENCHMARK_VERSION,
    DEFAULT_TASK_ROOT,
    load_task,
    load_tasks,
)


_PIPELINE_SUCCESS_STATUSES = frozenset({"complete_success", "success_with_warnings"})


def _workspace_inventory_representation_contract(
    paths: list[str],
    sizes: dict[str, int] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Describe path representations without reading or claiming file content."""

    textual_application_types = {
        "application/csv",
        "application/javascript",
        "application/json",
        "application/sql",
        "application/toml",
        "application/xml",
        "application/x-ndjson",
        "application/x-yaml",
    }
    entries: list[dict[str, Any]] = []
    known_text = 0
    known_non_text = 0
    unknown = 0
    extensions: set[str] = set()
    for path in paths:
        extension = Path(path).suffix.lower()
        media_type = mimetypes.guess_type(path)[0]
        if extension:
            extensions.add(extension)
        if media_type is None:
            compatibility = "unknown"
            unknown += 1
        elif media_type.startswith("text/") or media_type in textual_application_types:
            compatibility = "compatible"
            known_text += 1
        else:
            compatibility = "incompatible"
            known_non_text += 1
        entries.append({
            "path": path,
            **({"byte_size": sizes[path]} if sizes and path in sizes else {}),
            "extension": extension,
            "media_type": media_type,
            "text_reader_compatibility": compatibility,
            "content_status": "not_read",
            "read_requirement": "read_file_before_using_content",
        })
    contract = {
        "contract_kind": "workspace_file_inventory",
        "coverage": "complete_path_list_content_unread",
        "inventory_artifact_role": "framework_metadata_only",
        "working_directory": "/app",
        "authorized_runtime_paths": list(paths),
        "tool_binding_rule": (
            "The inventory artifact handle names this metadata JSON, not any "
            "inventoried file. Bind a Tool file or argument port to an exact literal "
            "path from authorized_runtime_paths."
        ),
        "generated_process_path_rule": (
            "A generated program receives task paths as arguments and resolves them "
            "from its actual process working directory; it must not hard-code /app."
        ),
        "file_count": len(paths),
        "known_text_file_count": known_text,
        "known_non_text_file_count": known_non_text,
        "unknown_media_type_count": unknown,
        "extensions": sorted(extensions),
        "content_facts_available": False,
        **({"known_size_file_count": len(sizes),
            "total_known_file_bytes": sum(sizes.values()),
            "largest_known_file_bytes": max(sizes.values(), default=0)} if sizes else {}),
    }
    return contract, entries


def _verified_success(
    *,
    pipeline_status: str,
    verifier: dict[str, Any] | None,
    failure: dict[str, Any] | None,
) -> bool:
    """Return the official benchmark outcome, not merely process completion."""

    if pipeline_status not in _PIPELINE_SUCCESS_STATUSES or failure is not None:
        return False
    if not verifier or verifier.get("status") != "ok":
        return False
    try:
        return verifier.get("reward") is not None and float(verifier["reward"]) > 0.0
    except (TypeError, ValueError):
        return False


def _run_dir(root: Path, task_id: str, trial_id: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{task_id}__{trial_id}"
    if path.exists():
        raise RuntimeError(f"run directory already exists: {path}")
    path.mkdir(parents=True)
    return path


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _worker_command(
    args: argparse.Namespace, run_dir: Path, trial_id: str,
    *, method_deadline_monotonic: float | None = None,
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "sgar_mvp.scripts.external_substrate_worker",
        "--config",
        str(Path(args.config).resolve()),
        "--query",
        args.query,
        "--output-dir",
        str(run_dir / "native"),
        "--report-path",
        str(run_dir / "native" / "experiment_report.md"),
        "--run-id",
        trial_id,
        "--trial-id",
        trial_id,
        "--task-state-manifest",
        str(run_dir / "task_state_manifest.json"),
        "--network-policy",
        "declared" if args.network else "disabled",
        *(["--max-generation-requests", str(args.max_generation_requests)]
          if args.max_generation_requests is not None else []),
        *(["--max-embedding-requests", str(args.max_embedding_requests)]
          if args.max_embedding_requests is not None else []),
        *(["--method-deadline-monotonic", str(method_deadline_monotonic)]
          if method_deadline_monotonic is not None else []),
    ]


def _instruction_file_paths(instruction: str) -> tuple[str, ...]:
    """Locate explicit path spellings; existence and content remain runtime facts."""

    text = re.sub(r"https?://[^\s`\"'<>]+", "", instruction)
    quoted = re.findall(r"`([^`]+)`|\"([^\"]+)\"|'([^']+)'", text)
    paths = {value for group in quoted for value in group if value.startswith("/")}
    text = re.sub(r"`[^`]+`|\"[^\"]+\"|'[^']+'", "", text)
    paths.update(match.rstrip(".:") for match in re.findall(
        r"(?<![\w:/])(/[^\s`\"'<>|;,()\[\]{}]+)", text,
    ))
    return tuple(sorted({posixpath.normpath(path) for path in paths
                         if path != "/" and not path.startswith("//")
                         and not any(character in path for character in "\x00\n\r")}))


def _task_state_manifest(
    task: Any,
    output_dir: Path,
    *,
    physical_working_dir: str | None = None,
    runtime: DockerTaskRuntime | None = None,
) -> dict[str, Any]:
    """Describe declared inputs and files present in the live task workspace.

    This is benchmark-adapter metadata only.  It never changes the image's
    original files.  Declared COPY inputs retain their individual handles;
    discovered workspace state is one inventory handle whose paths must be
    inspected in the task container before their contents can be used.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    dockerfile = task.task_dir / "environment" / "Dockerfile"
    workdir = "/workspace"
    task_root = posixpath.normpath(str(physical_working_dir or workdir))
    records: list[dict[str, str]] = []
    if dockerfile.is_file():
        for raw in dockerfile.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            work_match = re.match(r"WORKDIR\s+(.+)$", line, re.IGNORECASE)
            if work_match:
                workdir = posixpath.normpath(work_match.group(1).strip())
                continue
            copy_match = re.match(r"COPY\s+([^\s]+)\s+([^\s]+)\s*$", line, re.IGNORECASE)
            if not copy_match:
                continue
            source_name, target = copy_match.groups()
            source = (task.task_dir / "environment" / source_name).resolve()
            try:
                source.relative_to((task.task_dir / "environment").resolve())
            except ValueError:
                continue
            if not source.is_file() or (source.suffix.lower() not in {".txt", ".md", ".py", ".v", ".tex", ".js", ".ts", ".json", ".csv", ".sql"}
                                       and not is_model_media_path(source.name)):
                continue
            target_path = target if target.startswith("/") else posixpath.join(workdir, target)
            target_path = posixpath.normpath(target_path)
            # Docker treats ``COPY file .`` and a destination that names the
            # current WORKDIR as directory copies.  Resolve the simple
            # single-file form here so the public handle names the actual
            # file, rather than the directory that contains it.
            destination_is_directory = (
                target.endswith("/")
                or target in {".", "./"}
                or target_path == workdir
            )
            if destination_is_directory:
                target_path = posixpath.join(
                    target_path, posixpath.basename(source_name.rstrip("/"))
                )
            # Only expose inputs available under the image's actual final
            # working directory.  Files copied to build or system locations
            # remain image internals and must not be advertised as task input
            # handles.  This is path-neutral: /workspace, /app, /root, etc.
            # are all handled through the same logical /app mapping.
            if target_path != task_root and not target_path.startswith(task_root + "/"):
                continue
            logical_name = posixpath.basename(target_path)
            if not logical_name or logical_name in {".", ".."}:
                continue
            records.append({
                "logical_name": logical_name,
                # The frozen benchmark package is the authorized source root.
                # prepare_task_invocation snapshots it into the run directory
                # before any model call; keeping this path outside output_dir
                # also preserves the input/output separation invariant.
                "source_path": str(source),
                # Preserve Docker COPY's source basename.  Public input
                # descriptors use this name in /app/inputs/<logical_name>/;
                # the image target basename is represented by target_path.
                "source_name": source.name,
                "target_path": target_path,
                # The runtime maps this image-local path to the stable SGAR
                # logical namespace after inspecting the image WORKDIR.
                "logical_target_path": target_path,
            })
    # Dockerfile COPY is incomplete: a RUN command can create task state.
    # Discover files in the already-started working directory. A
    # directory's contents are operational state, not a set of independent
    # mandatory inputs: exposing every discovered file as a public handle
    # would force Planner and Compiler to bind unrelated metadata (including
    # binary repository internals) before any Tool can inspect the workspace.
    # The benchmark mounts verifier files later outside /app.
    inventory_status = "not_requested"
    inventory_paths: list[str] = []
    inventory_sizes: dict[str, int] = {}
    if runtime is not None:
        inventory_status = "available"
        try:
            found = runtime.exec_argv(
                ["find", ".", "-type", "f", "-printf", "%s\t%p\\0"],
                timeout=30,
                cwd="/app",
            )
            # BusyBox find need not implement -printf. Optional size metadata
            # must not prevent task startup or change authorized paths.
            if not found.get("ok"):
                found = runtime.exec_argv(
                    ["find", ".", "-type", "f", "-print0"], timeout=30, cwd="/app",
                )
            if not found.get("ok"):
                inventory_status = "unavailable"
            else:
                raw_paths = str(found.get("stdout") or "")
                declared_targets = {
                    _logical_task_path(item["target_path"],
                                       physical_working_dir=physical_working_dir)
                    for item in records
                }
                for item in raw_paths.split("\x00"):
                    if not item:
                        continue
                    size = None
                    prefix, separator, suffix = item.partition("\t")
                    if separator and prefix.isascii() and prefix.isdigit():
                        size, item = int(prefix), suffix
                    if not item.startswith("./") or "\n" in item or "\r" in item:
                        continue
                    logical = posixpath.normpath("/app/" + item[2:])
                    if (
                        logical.startswith("/app/")
                        and not logical.startswith("/app/inputs/")
                        and logical not in declared_targets
                    ):
                        inventory_paths.append(logical)
                        if size is not None:
                            inventory_sizes[logical] = size
                inventory_paths = sorted(set(inventory_paths))
        except (OSError, subprocess.SubprocessError, TaskRuntimeError, UnicodeError):
            inventory_status = "unavailable"

        # Task instructions can name existing inputs outside WORKDIR. Probe
        # those exact files, without scanning their parents or treating missing
        # output paths as missing inputs. Keep all ordinary workspace handling.
        external_paths = tuple(sorted({
            _logical_task_path(path, physical_working_dir=physical_working_dir)
            for path in _instruction_file_paths(str(task.instruction))
            if not _logical_task_path(path, physical_working_dir=physical_working_dir).startswith("/app/")
            and _logical_task_path(path, physical_working_dir=physical_working_dir) != "/app"
        }))
        verified_external_paths: set[str] = set()
        if external_paths:
            try:
                found = runtime.exec_argv(
                    ["find", *external_paths, "-maxdepth", "0", "-type", "f",
                     "-printf", "%s\t%p\\0"], timeout=30, cwd="/app",
                )
                # A nonexistent requested output may make find exit nonzero
                # while it still reports real inputs. Parse verified output;
                # unsupported -printf can fall back to path-only discovery.
                raw = str(found.get("stdout") or "")
                if not found.get("ok") and not raw:
                    found = runtime.exec_argv(
                        ["find", *external_paths, "-maxdepth", "0", "-type", "f", "-print0"],
                        timeout=30, cwd="/app",
                    )
                    raw = str(found.get("stdout") or "")
                for item in raw.split("\x00"):
                    size = None
                    prefix, separator, suffix = item.partition("\t")
                    if separator and prefix.isascii() and prefix.isdigit():
                        size, item = int(prefix), suffix
                    if item in external_paths:
                        verified_external_paths.add(item)
                        inventory_paths.append(item)
                        if size is not None:
                            inventory_sizes[item] = size
                inventory_paths = sorted(set(inventory_paths))
            except (OSError, subprocess.SubprocessError, TaskRuntimeError, UnicodeError):
                # This optional discovery must not disable the workspace route.
                pass

        # Supported model media needs real bytes as well as an inventory path.
        # Expose independent optional materials; Planner still chooses which
        # inputs a node consumes. Ordinary repository files remain inventory.
        media_records = []
        source_dir = output_dir.parent / (output_dir.name + ".task-state-source")
        source_dir.mkdir(parents=False, exist_ok=False)
        declared_media = {_logical_task_path(record["target_path"], physical_working_dir=physical_working_dir): record
                          for record in records if is_model_media_path(record["source_path"])}
        for logical in sorted(set(inventory_paths) | set(declared_media)):
            if not is_model_media_path(logical) or any(part in {".git", ".hg", ".svn", ".agents", ".codex"}
                                                       for part in Path(logical).parts):
                continue
            name = "media_" + hashlib.sha256(logical.encode()).hexdigest()[:12] + Path(logical).suffix.lower()
            snapshot = source_dir / name
            snapshot_options = ({"authorized_paths": verified_external_paths}
                                if logical in verified_external_paths else {})
            if not runtime.snapshot_task_file(logical, snapshot, max_bytes=MAX_MODEL_MEDIA_BYTES,
                                              **snapshot_options):
                continue
            if logical in declared_media:
                declared_media[logical].update(source_path=str(snapshot), source_name=name)
                continue
            media_records.append({"logical_name": name, "source_path": str(snapshot),
                "source_name": name, "target_path": logical, "logical_target_path": logical,
                "execution_contract": {"contract_kind": "task_media_snapshot",
                    "original_task_path": logical, "selection": "optional",
                    "content_facts_available": True}})

        # This manifest is a public input descriptor, not a claim about
        # file contents.  A later Tool must read an indicated task path
        # before the plan may use facts from that file.
        source = source_dir / "task_environment_inventory.json"
        representation_contract, inventory_entries = (
            _workspace_inventory_representation_contract(inventory_paths, inventory_sizes)
        )
        _write(source, {
            "protocol": "sgar-task-container-inventory-v1",
            "status": inventory_status,
            "working_directory": "/app",
            "path_contract": {
                "tool_logical_workspace_root": "/app",
                **({"task_declared_external_paths": sorted(verified_external_paths),
                    "external_path_rule": "Exact inventory paths outside /app are image-local task inputs; pass them unchanged in declared Tool path/argument ports."}
                   if verified_external_paths else {}),
                "tool_path_rule": (
                    "Use /app paths only in declared Tool path or cwd arguments; "
                    "the runtime maps that logical namespace into the task image."
                ),
                "generated_process_cwd_rule": (
                    "Generated programs must resolve task files from their actual "
                    "process working directory (for example os.getcwd() or relative "
                    "paths) and must not hard-code the logical /app root internally."
                ),
            },
            "execution_context": "live_task_runtime",
            "instruction_authority": "original_task",
            "delivery_note": "This is an execution environment. Follow the original task delivery requirements; a written guide does not substitute for requested runtime changes.",
            "total_file_count": len(inventory_paths),
            "omitted_file_count": 0,
            "captured_text_file_count": 0,
            "representation_contract": representation_contract,
            "files": inventory_entries,
        })
        records.append({
            "logical_name": "task_environment_inventory",
            "source_path": str(source),
            "source_name": source.name,
            "target_path": "/app/inputs/task_environment_inventory/" + source.name,
            "logical_target_path": "/app/inputs/task_environment_inventory/" + source.name,
            "execution_contract": representation_contract,
        })
        records.extend(media_records)
    payload = {
        "protocol": "sgar-tb21-task-state-manifest-v1",
        "records": records,
        "inventory_status": inventory_status,
        "inventory_file_count": len(inventory_paths),
        "final_deliverable_contract": _task_final_deliverable_contract(task),
    }
    _write(output_dir / "task_state_manifest.json", payload)
    return payload


def _logical_task_path(path: str, *, physical_working_dir: str | None) -> str:
    """Map an image path back into SGAR's stable /app namespace."""

    normalized = posixpath.normpath(str(path))
    physical = posixpath.normpath(str(physical_working_dir or "/app"))
    if normalized == physical:
        return "/app"
    if normalized.startswith(physical + "/"):
        return "/app" + normalized[len(physical):]
    if normalized == "/app" or normalized.startswith("/app/"):
        return normalized
    return normalized


def _requested_output_in_clause(prefix: str) -> bool:
    """Recognize requested writes, not historical descriptions of supplied state.

    Ambiguous narrative is left to Planner with the unchanged task instruction;
    it must not become an authoritative output override in the adapter.
    """
    clause = re.split(r"[.!?;]\s+", prefix)[-1].strip()
    clause = re.sub(r"^(?:[-*+]\s+|\d+[.)]\s+)", "", clause)
    clause = clause.lstrip("*` ")
    verbs = r"(?:create|write|save|generate|produce|place|store|deliver|output|implement|put|leave|export|compile|build|convert)"
    requested = re.search(
        rf"^(?:please\s+)?{verbs}\b|\b(?:must|should|need\s+to|have\s+to)\s+{verbs}\b",
        clause, re.IGNORECASE,
    )
    # A stated task goal can coordinate an analysis with a requested write.
    # Still require a delivery action nearest the path so inspected inputs
    # and descriptions of supplied state do not acquire output authority.
    task_goal = re.match(
        r"^(?:(?:the|your)\s+)?(?:goal|objective|task)\s+is\s+to\b",
        clause, re.IGNORECASE,
    )
    if not requested and not task_goal:
        return re.search(
            r"\b(?:final|output|result|deliverable)\b.*\b(?:must|should)\s+be\s+(?:in|at|under)\b",
            clause, re.IGNORECASE,
        ) is not None
    # A later input-acquisition verb starts another relation to the path.
    actions = list(re.finditer(
        rf"\b({verbs}|read(?:ing)?|inspect(?:ing)?|load(?:ing)?|consum(?:e|ing)|processed\s+(?:by|with))\b",
        clause, re.IGNORECASE,
    ))
    return bool(actions) and not actions[-1].group(1).casefold().startswith(
        ("read", "inspect", "load", "consum", "processed")
    )


def _explicit_workspace_output_paths(text: str) -> list[tuple[str, bool]]:
    """Return explicit ``/app`` outputs declared by authoritative task text.

    Output scope follows the task's grammar: a path is authoritative when it is
    in a Deliverables section, follows a mutation/delivery verb in its clause,
    or belongs to an indented file list introduced by such a clause.  Merely
    being a provided/read input never makes a path a final deliverable.
    """

    path_pattern = re.compile(
        r"(?<![A-Za-z0-9_.-])(/app(?:/[A-Za-z0-9_.+@-]+)+/?)(?![A-Za-z0-9_.+@/-])"
    )
    output_noun = re.compile(
        r"\b(?:files?|directories|directory|outputs?|results?|artifacts?|deliverables?)\b",
        re.IGNORECASE,
    )
    deliverables_match = re.search(
        r"(?ims)^\s*(?:#{1,6}\s*)?\*{0,2}deliverables?\*{0,2}\s*$\s*"
        r"(.*?)(?=^\s*(?:#{1,6}\s+|\*\*[A-Za-z][^*]+\*\*\s*$)|\Z)",
        text,
    )
    deliverables_span = (
        (deliverables_match.start(1), deliverables_match.end(1))
        if deliverables_match
        else None
    )

    declared: list[tuple[str, bool]] = []
    output_block_indent: int | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        visible = line.rstrip("\r\n")
        stripped = visible.strip()
        indent = len(visible) - len(visible.lstrip())
        if output_block_indent is not None and stripped:
            is_bullet = bool(re.match(r"^\s*[-*+]\s+", visible))
            if indent <= output_block_indent and not is_bullet:
                output_block_indent = None
        inherited_output_scope = output_block_indent is not None

        for match in path_pattern.finditer(visible):
            absolute_start = offset + match.start()
            in_deliverables = bool(
                deliverables_span
                and deliverables_span[0] <= absolute_start < deliverables_span[1]
            )
            prefix = visible[: match.start()]
            if not (
                in_deliverables
                or inherited_output_scope
                or _requested_output_in_clause(prefix)
            ):
                continue
            raw_path = match.group(1).rstrip(".,;:")
            is_directory = raw_path.endswith("/")
            path = posixpath.normpath(raw_path)
            if path == "/app" or not path.startswith("/app/"):
                continue
            item = (path, is_directory)
            if item not in declared:
                declared.append(item)

        if (
            stripped.endswith(":")
            and _requested_output_in_clause(visible)
            and output_noun.search(visible)
        ):
            output_block_indent = indent
        offset += len(line)

    # A parent directory is an obligation, but its explicitly named child files
    # are the enforceable bundle members.  Keep a directory only when it is the
    # sole declared output beneath that path.
    filtered: list[tuple[str, bool]] = []
    for path, is_directory in declared:
        if is_directory and any(
            other != path and other.startswith(path.rstrip("/") + "/")
            for other, _ in declared
        ):
            continue
        filtered.append((path, is_directory))
    return filtered


def _task_final_deliverable_contract(task: Any) -> dict[str, Any] | None:
    """Extract explicit workspace delivery without verifier introspection."""

    text = str(getattr(task, "instruction", "") or "")
    declared = _explicit_workspace_output_paths(text)
    absolute_paths = [path for path, _ in declared]
    if len(absolute_paths) > 1:
        return {
            "representation": "bundle",
            "format_id": "bundle",
            "media_type": "application/x.sgar-artifact-bundle",
            "extension": "",
            "logical_name": "task-deliverables",
            "required_members": [
                path.removeprefix("/app/") for path in absolute_paths
            ],
        }
    if len(absolute_paths) == 1:
        path, is_directory = declared[0]
        logical_name = posixpath.basename(path)
        if is_directory:
            return {
                "representation": "directory",
                "format_id": "directory",
                "media_type": "inode/directory",
                "extension": "",
                "logical_name": logical_name,
                "runtime_path": path,
            }
        extension = Path(logical_name).suffix.lower()
        return {
            "representation": "file",
            "format_id": extension.removeprefix(".") or "file",
            "media_type": "application/octet-stream",
            "extension": extension,
            "logical_name": logical_name,
            "runtime_path": path,
        }

    # Retain the historical relative-name fallback for tasks that do not name an
    # absolute workspace output.  Nearby delivery language remains mandatory.
    pattern = re.compile(
        r"\b([A-Za-z0-9][A-Za-z0-9_.-]*\.(?:vo|tex|pdf|jsonl?|csv|md|markdown|txt|py|js|ts))\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        if not _requested_output_in_clause(text[line_start : match.start()]):
            continue
        logical_name = match.group(1)
        extension = Path(logical_name).suffix.lower()
        return {
            "representation": "file",
            "format_id": extension.removeprefix(".") or "file",
            "media_type": "application/octet-stream",
            "extension": extension,
            "logical_name": logical_name,
        }
    return None


def _effective_agent_timeout(args: argparse.Namespace, task: Any) -> float | None:
    """Resolve the method timeout without changing the benchmark metadata."""

    if bool(getattr(args, "no_agent_timeout", False)):
        return None
    override = getattr(args, "agent_timeout", None)
    if override is not None:
        value = float(override)
        if value <= 0:
            raise ValueError("agent_timeout_must_be_positive")
        return value
    return float(task.agent_timeout_sec)


def run_one(args: argparse.Namespace) -> dict[str, Any]:
    task = load_task(Path(args.task_root), args.task_id)
    agent_timeout = _effective_agent_timeout(args, task)
    trial_id = args.trial_id or f"{task.task_id}-{int(time.time())}"
    root = Path(args.output_root).resolve()
    run_dir = _run_dir(root, task.task_id, trial_id)
    runtime = DockerTaskRuntime(task, trial_id=trial_id, output_dir=run_dir)
    setup_started = time.monotonic()
    manifest = {
        "protocol": "sgar-tb21-trial-manifest-v1",
        "experiment_id": args.experiment_id,
        "benchmark_id": CANONICAL_BENCHMARK_ID,
        "benchmark_version": CANONICAL_BENCHMARK_VERSION,
        "task_id": task.task_id,
        "trial_id": trial_id,
        "task_hash": task.task_hash,
        "agent_timeout_sec": agent_timeout,
        "agent_timeout_policy": "disabled" if agent_timeout is None else "enforced",
        "verifier_timeout_sec": task.verifier_timeout_sec,
        "network_policy": "declared" if args.network else "disabled",
        "proxy_policy": "sgar-experiment-network-v1",
        "max_generation_requests": args.max_generation_requests,
        "max_embedding_requests": args.max_embedding_requests,
    }
    _write(run_dir / "trial_manifest.json", manifest)
    container_info: dict[str, Any] = {}
    worker: subprocess.Popen[str] | None = None
    worker_terminal: dict[str, Any] | None = None
    verifier: dict[str, Any] | None = None
    method_started = time.monotonic()
    method_ended = method_started
    failure: dict[str, Any] | None = None
    framework_success = False
    framework_failure: dict[str, Any] | None = None
    method_finished = False
    try:
        container_info = runtime.start()
        _task_state_manifest(
            task,
            run_dir,
            physical_working_dir=runtime.working_dir,
            runtime=runtime,
        )
        state_manifest = json.loads((run_dir / "task_state_manifest.json").read_text())
        for record in state_manifest.get("records", []):
            source = Path(record["source_path"])
            target = f"/app/inputs/{record['logical_name']}/{record['source_name']}"
            if source.is_file():
                staged = runtime.write_file(target, source)
                if not staged.get("ok"):
                    raise TaskRuntimeError("task_state_input_stage_failed")
            # Official task images normally already contain their initial
            # environment files.  Verify that the logical target resolves to
            # the image WORKDIR; if an image omits a copied file, restore the
            # frozen task-package bytes into that same container namespace.
            target_path = str(record.get("logical_target_path") or "")
            logical_target = _logical_task_path(
                target_path, physical_working_dir=runtime.working_dir
            )
            if logical_target.startswith(("/app/", "/tmp/")):
                present = runtime.exists(logical_target)
                if not present.get("exists", False) and source.is_file():
                    restored = runtime.write_file(logical_target, source)
                    if not restored.get("ok"):
                        raise TaskRuntimeError("task_state_target_restore_failed")
        manifest.update({"container": container_info, "setup_seconds": time.monotonic() - setup_started})
        _write(run_dir / "trial_manifest.json", manifest)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path.cwd()) + os.pathsep + env.get("PYTHONPATH", "")
        env["SGAR_PROJECT_ROOT"] = str(Path.cwd().resolve())
        (run_dir / "native").mkdir(parents=True, exist_ok=True)
        method_started = time.monotonic()
        deadline = None if agent_timeout is None else method_started + agent_timeout
        worker = subprocess.Popen(
            _worker_command(args, run_dir, trial_id, method_deadline_monotonic=deadline),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=(run_dir / "native" / "worker.stderr.log").open("w", encoding="utf-8"),
            text=True,
            bufsize=1,
            env=env,
        )
        assert worker.stdin is not None and worker.stdout is not None
        timed_out = False
        with (run_dir / "rpc_actions.jsonl").open("w", encoding="utf-8") as rpc_log:
            while True:
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    timed_out = True
                    break
                ready, _, _ = select.select([worker.stdout], [], [], remaining)
                if not ready:
                    timed_out = True
                    break
                line = worker.stdout.readline()
                if not line:
                    break
                payload = json.loads(line)
                if payload.get("protocol") == "sgar-external-substrate-action-v1":
                    result = runtime.handle_rpc(payload)
                    response = {
                        "protocol": "sgar-external-substrate-result-v1",
                        "run_id": payload.get("run_id"),
                        "trial_id": payload.get("trial_id"),
                        "action_id": payload.get("action_id"),
                        "result": result,
                    }
                    rpc_log.write(json.dumps({"request": payload, "result": result}, ensure_ascii=False) + "\n")
                    rpc_log.flush()
                    worker.stdin.write(json.dumps(response, ensure_ascii=False) + "\n")
                    worker.stdin.flush()
                    continue
                if payload.get("protocol") == "sgar-external-substrate-terminal-v1":
                    worker_terminal = payload
                    _write(run_dir / "worker_terminal.json", payload)
                    break
        method_ended = time.monotonic()
        if timed_out:
            failure = {
                "failure_class": "timeout",
                "detail": f"agent_timeout_{agent_timeout}s",
            }
            if worker.poll() is None:
                worker.kill()
                worker.wait(timeout=30)
        if worker.poll() is None:
            worker.stdin.close()
            worker.wait(timeout=30)
        if worker.returncode != 0 and not timed_out:
            failure = {"failure_class": "method_failure", "detail": f"worker_exit_{worker.returncode}"}
        if worker_terminal is None:
            failure = failure or {
                "failure_class": "method_failure",
                "detail": "worker_terminal_missing",
            }
        else:
            worker_status = str(worker_terminal.get("status") or "")
            worker_result = worker_terminal.get("result")
            worker_result = worker_result if isinstance(worker_result, dict) else {}
            pipeline_status = str(worker_result.get("pipeline_status") or "")
            if worker_status != "completed":
                failure = failure or {
                    "failure_class": "method_failure",
                    "detail": f"worker_status:{worker_status or 'missing'}",
                }
            elif pipeline_status not in _PIPELINE_SUCCESS_STATUSES:
                failure = failure or {
                    "failure_class": "method_failure",
                    "detail": f"pipeline_status:{pipeline_status or 'missing'}",
                }
        # Freeze execution outcome before the independent verifier phase.
        # Verifier transport/setup failure cannot undo an already completed
        # method, and an official pass cannot complete a failed method.
        framework_failure = failure
        framework_success = failure is None
        method_finished = True
        verifier_started = time.monotonic()
        verifier = runtime.verify()
        verifier["verifier_seconds"] = time.monotonic() - verifier_started
        _write(run_dir / "verifier.json", verifier)
        (run_dir / "verifier_stdout.log").write_text(
            str(verifier.get("stdout") or ""), encoding="utf-8"
        )
        (run_dir / "verifier_stderr.log").write_text(
            str(verifier.get("stderr") or verifier.get("detail") or ""), encoding="utf-8"
        )
        if verifier.get("status") != "ok":
            failure = {"failure_class": "verifier_failure", "detail": verifier.get("status")}
    except (TaskRuntimeError, subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as exc:
        failure = {"failure_class": "infrastructure_failure", "detail": f"{type(exc).__name__}:{exc}"}
        if not method_finished:
            framework_failure = failure
            method_ended = time.monotonic()
        if worker is not None and worker.poll() is None:
            worker.kill()
            worker.wait()
    finally:
        cleanup_started = time.monotonic()
        cleanup = runtime.cleanup()
        total = time.monotonic() - setup_started

    worker_result = (
        worker_terminal.get("result")
        if isinstance(worker_terminal, dict)
        and isinstance(worker_terminal.get("result"), dict)
        else {}
    )
    pipeline_status = str(worker_result.get("pipeline_status") or "")
    reward = verifier.get("reward") if verifier else None
    verified_success = _verified_success(
        pipeline_status=pipeline_status,
        verifier=verifier,
        failure=failure,
    )
    result = {
        **manifest,
        "method_wall_clock_seconds": method_ended - method_started,
        "e2e_wall_clock_seconds": total,
        "verifier": verifier,
        "cleanup": cleanup,
        "worker_status": worker_terminal.get("status") if worker_terminal else None,
        "pipeline_status": pipeline_status or None,
        "verifier_status": verifier.get("status") if verifier else None,
        "framework_success": framework_success,
        "framework_failure": framework_failure,
        "verified_success": verified_success,
        # `success` is the benchmark outcome used by batch aggregation.  The
        # verifier process being runnable is recorded separately above.
        "success": verified_success,
        "official_reward": reward,
        "failure": failure,
        "native_run_dir": str(run_dir / "native"),
        "rpc_log_path": str(run_dir / "rpc_actions.jsonl"),
    }
    _write(run_dir / "result.json", result)
    return result


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    tasks, tree_hash = load_tasks(Path(args.task_root))
    selected = tasks if args.task_id in {None, "all"} else [
        load_task(Path(args.task_root), args.task_id)
    ]
    records = []
    for task in selected:
        runtime = DockerTaskRuntime(
            task,
            trial_id=f"preflight-{task.task_id}",
            output_dir=Path(args.output_root),
        )
        records.append(
            {
                "task_id": task.task_id,
                "image": task.image,
                "image_digest": runtime.image_digest(),
                "task_hash": task.task_hash,
            }
        )
    return {
        "protocol": "sgar-tb21-preflight-v1",
        "benchmark_id": CANONICAL_BENCHMARK_ID,
        "benchmark_version": CANONICAL_BENCHMARK_VERSION,
        "task_tree_sha256": tree_hash,
        "task_count": len(records),
        "images": records,
    }


def run_batch(args: argparse.Namespace) -> int:
    manifest = preflight(args)
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "preflight.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    results = []
    for item in manifest["images"][: args.max_tasks or None]:
        task_args = argparse.Namespace(**vars(args))
        task_args.task_id = item["task_id"]
        results.append(run_one(task_args))
    summary = {
        "protocol": "sgar-tb21-batch-result-v1",
        "task_tree_sha256": manifest["task_tree_sha256"],
        "results": results,
        "succeeded": sum(bool(item.get("success")) for item in results),
        "failed": sum(not bool(item.get("success")) for item in results),
    }
    (output_root / "batch_result.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one SGAR native TB2.1 task")
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--task-root", default=str(DEFAULT_TASK_ROOT))
    parser.add_argument("--output-root", required=False, default="/tmp/sgar-tb21")
    parser.add_argument("--config", default="sgar_mvp/config.json")
    parser.add_argument("--query", default=None)
    parser.add_argument("--trial-id", default=None)
    parser.add_argument("--experiment-id", default="sgar-tb21")
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument(
        "--agent-timeout",
        type=float,
        default=None,
        help="Override the task agent timeout in seconds.",
    )
    parser.add_argument(
        "--no-agent-timeout",
        action="store_true",
        help="Disable the SGAR method timeout for a diagnostic run.",
    )
    parser.add_argument("--max-generation-requests", type=int, default=None)
    parser.add_argument(
        "--max-embedding-requests",
        type=int,
        default=DEFAULT_MAX_EMBEDDING_REQUESTS,
        help="Optional diagnostic cap on per-trial embedding requests.",
    )
    parser.add_argument("inventory", nargs="?", choices=("inventory",))
    args = parser.parse_args()
    if args.inventory:
        tasks, tree_hash = load_tasks(Path(args.task_root))
        print(json.dumps({"tasks": len(tasks), "task_tree_sha256": tree_hash}, indent=2))
        return 0
    if args.task_id in {None, "all"}:
        return run_batch(args)
    if not args.task_id:
        parser.error("--task-id is required for a task run")
    if args.query is None:
        args.query = load_task(Path(args.task_root), args.task_id).instruction
    result = run_one(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
