"""No-provider compatibility probe for the generic public-input boundary."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from .authorized_material import (
    AuthorizedMaterialError,
    AuthorizedMaterialSource,
    build_authorized_model_material_view,
    public_snapshot_identity,
)
from .payload_provenance import PayloadSourceRegistry, ProductionModelPayloadGuard
from .pipeline_control import (
    SubtaskRevisionRef,
    canonical_json_bytes,
    canonical_sha256,
    subtask_revision_identity_sha256,
)
from .schema import ArtifactHandle
from .task_invocation import (
    InputSnapshotPolicy,
    InputSourceSpec,
    prepare_task_invocation,
    verify_prepared_task_invocation,
)


INPUT_COMPATIBILITY_PROTOCOL = "sgar-input-compatibility-probe-v1"


def _cleanup_probe_root(root: Path, *, preserve_active_exception: bool) -> None:
    target = str(root)
    if sys.platform == "win32" and root.is_absolute() and not target.startswith("\\\\?\\"):
        target = f"\\\\?\\{target}"
    try:
        shutil.rmtree(target)
    except OSError:
        if not preserve_active_exception:
            raise


def run_generic_input_compatibility_probe(
    work_dir: str | Path,
    *,
    scratch_parent: str | Path | None = None,
) -> dict[str, Any]:
    """Exercise every supported input shape through the shared production contracts."""

    parent = Path(scratch_parent or work_dir).resolve() / "ic"
    parent.mkdir(parents=True, exist_ok=True)
    root = parent / uuid.uuid4().hex[:8]
    root.mkdir(parents=True, exist_ok=False)
    try:
        fixtures = root / "f"
        fixtures.mkdir()
        text_path = fixtures / "plain.txt"
        csv_path = fixtures / "tabular.csv"
        json_path = fixtures / "structured.json"
        binary_path = fixtures / "opaque.bin"
        directory_path = fixtures / "tree"
        empty_path = fixtures / "empty.txt"
        large_path = fixtures / "large.txt"
        malformed_path = fixtures / "malformed.json"
        dependency_path = fixtures / "dependency.json"

        text_path.write_text("generic text payload\n", encoding="utf-8")
        csv_path.write_text("column_a,column_b\n1,alpha\n", encoding="utf-8")
        json_path.write_text('{"enabled":true,"items":[1,2]}', encoding="utf-8")
        binary_path.write_bytes(b"\x00\xff\x10\x80")
        (directory_path / "nested").mkdir(parents=True)
        (directory_path / "nested" / "member.txt").write_text("member", encoding="utf-8")
        (directory_path / "empty").mkdir()
        empty_path.write_bytes(b"")
        large_path.write_text("large-input-block\n" * 6000, encoding="utf-8")
        malformed_path.write_text('{"incomplete":', encoding="utf-8")
        dependency_path.write_text('{"upstream":"committed"}', encoding="utf-8")

        ordered = (
            ("text", text_path),
            ("csv", csv_path),
            ("json", json_path),
            ("binary", binary_path),
            ("directory", directory_path),
            ("empty", empty_path),
            ("large", large_path),
            ("malformed", malformed_path),
        )
        invocation_root = root / "r"
        invocation_root.mkdir()
        prepared = prepare_task_invocation(
            query="Process the declared generic inputs through shared contracts.",
            input_specs=tuple(
                InputSourceSpec(logical_name=name, source_path=path)
                for name, path in ordered
            ),
            run_dir=invocation_root,
            request_id="compatibility-probe-request-v1",
            policy=InputSnapshotPolicy(inline_text_max_bytes=4096),
            allowed_public_input_roots=(fixtures,),
        )
        invocation_audit = verify_prepared_task_invocation(prepared)
        descriptors = {
            item.handle_id: item for item in prepared.invocation.public_inputs
        }
        handles = tuple(
            ArtifactHandle.model_validate(item) for item in prepared.internal_handles()
        )
        public_sources: list[AuthorizedMaterialSource] = []
        for handle in handles:
            descriptor = descriptors[handle.handle_id]
            if not handle.host_path:
                raise RuntimeError("compatibility_probe_internal_handle_missing")
            public_sources.append(
                AuthorizedMaterialSource(
                    source_id=f"compatibility-public:{handle.handle_id}",
                    origin="public_input",
                    logical_name=descriptor.logical_name,
                    logical_locator=descriptor.runtime_path,
                    source_path=Path(handle.host_path),
                    expected_sha256=descriptor.content_sha256,
                    expected_byte_size=descriptor.byte_size,
                    expected_kind=descriptor.path_kind,
                    extension=descriptor.extension,
                    media_type=descriptor.media_type,
                )
            )

        malformed_source = public_sources[-1]
        authorized_sources = public_sources[:-1]
        malformed_input_rejected = False
        try:
            build_authorized_model_material_view(
                run_id="compatibility-probe-malformed-v1",
                revision=SubtaskRevisionRef(
                    graph_revision=1,
                    subtask_id="compatibility-malformed-node",
                    subtask_revision=0,
                ),
                sources=(malformed_source,),
                per_source_max_bytes=2048,
                total_max_bytes=2048,
            )
        except AuthorizedMaterialError as exc:
            malformed_input_rejected = (
                str(exc) == "authorized_material_descriptor_failed"
            )

        dependency_hash, dependency_size, dependency_kind = public_snapshot_identity(
            dependency_path
        )
        dependency_handle = ArtifactHandle(
            handle_id="committed-dependency-handle",
            kind="task_final",
            producer_task="producer-node",
            logical_path="context/producer-node/result.json",
            host_path=str(dependency_path),
            tool_path="/app/context/producer-node/result.json",
            artifact_type="json",
            validation_status="committed",
            current_run=True,
            path_kind="file",
            extension=".json",
            exists=True,
        )
        authorized_sources.append(
            AuthorizedMaterialSource(
                source_id="compatibility-committed:producer-node",
                origin="committed_dependency",
                logical_name="producer-node",
                logical_locator=str(dependency_handle.tool_path),
                source_path=Path(str(dependency_handle.host_path)),
                expected_sha256=dependency_hash,
                expected_byte_size=dependency_size,
                expected_kind=dependency_kind,
                extension=dependency_handle.extension,
                media_type="application/json",
            )
        )

        revision = SubtaskRevisionRef(
            graph_revision=1,
            subtask_id="compatibility-consumer-node",
            subtask_revision=0,
        )
        view = build_authorized_model_material_view(
            run_id="compatibility-probe-run-v1",
            revision=revision,
            sources=tuple(authorized_sources),
            per_source_max_bytes=2048,
            total_max_bytes=16 * 1024,
        )
        registry = PayloadSourceRegistry(
            subtask_id=revision.subtask_id,
            mode="compatibility_probe",
            attempt_id="attempt-0",
        )
        registry.register(
            "compatibility-invocation",
            origin="public_fixture",
            material=prepared.invocation.model_dump(mode="json"),
            default=True,
        )
        registry.register(
            "compatibility-authorized-material",
            origin="public_fixture",
            material=view.model_dump(mode="json"),
            default=True,
        )
        guard = ProductionModelPayloadGuard(registry)
        bound_guard = guard.for_request(
            "generic_input_compatibility",
            request_identity={
                "subtask_revision_sha256": subtask_revision_identity_sha256(revision)
            },
        )
        model_projection = {
            "protocol": INPUT_COMPATIBILITY_PROTOCOL,
            "subtask_revision_sha256": subtask_revision_identity_sha256(revision),
            "authorized_materials": view.model_dump(mode="json"),
            "input_descriptors": [
                {
                    "logical_locator": item.logical_locator,
                    "content_sha256": item.content_sha256,
                    "tree_sha256": item.tree_sha256,
                    "descriptor_sha256": item.descriptor_sha256,
                }
                for item in view.materials
            ],
        }
        payload = {
            "model": "compatibility-local-transport",
            "messages": [
                {
                    "role": "user",
                    "content": canonical_json_bytes(model_projection).decode("utf-8"),
                }
            ],
            "stream": False,
        }
        bound_guard(payload)
        serialized_payload = canonical_json_bytes(payload).decode("utf-8")
        serialized_public = canonical_json_bytes(
            prepared.invocation.model_dump(mode="json")
        ).decode("utf-8")
        by_name = {item.logical_name: item for item in view.materials}
        fixture_categories = [name for name, _path in ordered]
        valid = bool(
            invocation_audit["valid"]
            and len(handles) == len(ordered)
            and len(view.materials) == len(ordered)
            and all(name in by_name for name in fixture_categories[:-1])
            and by_name["binary"].evidence_kind == "descriptor_only"
            and by_name["directory"].representation == "directory"
            and by_name["large"].evidence_kind == "bounded"
            and by_name["empty"].authorized_content_bytes == 0
            and malformed_input_rejected
            and by_name["producer-node"].origin == "committed_dependency"
            and guard.checks
            and guard.checks[-1]["passed"] is True
            and str(root) not in serialized_payload
            and str(root) not in serialized_public
            and prepared.invocation.request_id not in serialized_payload
            and prepared.invocation.query not in serialized_payload
        )
        projection = {
            "protocol": INPUT_COMPATIBILITY_PROTOCOL,
            "valid": valid,
            "fixture_categories": fixture_categories,
            "public_input_count": len(handles),
            "authorized_material_count": len(view.materials),
            "dependency_origin_bound": by_name["producer-node"].origin
            == "committed_dependency",
            "binary_descriptor_only": by_name["binary"].evidence_kind
            == "descriptor_only",
            "directory_structure_bound": by_name["directory"].representation
            == "directory",
            "large_input_bounded": by_name["large"].evidence_kind == "bounded",
            "empty_input_preserved": by_name["empty"].authorized_content_bytes == 0,
            "malformed_input_rejected": malformed_input_rejected,
            "payload_guard_passed": bool(guard.checks and guard.checks[-1]["passed"]),
            "payload_host_free": str(root) not in serialized_payload,
            "request_metadata_absent": prepared.invocation.request_id
            not in serialized_payload
            and prepared.invocation.query not in serialized_payload,
            "invocation_sha256": prepared.invocation.invocation_sha256,
            "authorized_material_view_sha256": view.view_sha256,
            "payload_sha256": canonical_sha256(payload),
        }
        return {**projection, "probe_sha256": canonical_sha256(projection)}
    finally:
        _cleanup_probe_root(
            root,
            preserve_active_exception=sys.exc_info()[0] is not None,
        )


__all__ = [
    "INPUT_COMPATIBILITY_PROTOCOL",
    "run_generic_input_compatibility_probe",
]
