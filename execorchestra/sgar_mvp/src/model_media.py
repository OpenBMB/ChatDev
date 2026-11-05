"""Sealed projection of authorized binary materials into model message parts.

The formal ResourceCallRequest remains the authority for which bytes may cross
the provider boundary.  This adapter resolves only handles already bound to
that request, verifies their descriptor hash and size, and emits standard
OpenAI-compatible image/audio content parts without exposing host paths.
"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from .retrieval_runtime import load_applied_model_ready_state


MAX_MODEL_MEDIA_BYTES = 20 * 1024 * 1024

_IMAGE_MIME_BY_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
_AUDIO_FORMAT_BY_EXTENSION = {
    ".mp3": "mp3",
    ".wav": "wav",
}


class ModelMediaProjectionError(ValueError):
    """Fail-closed media projection error with a stable framework code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def is_model_media_path(path: str) -> bool:
    return Path(path).suffix.lower() in {*_IMAGE_MIME_BY_EXTENSION, *_AUDIO_FORMAT_BY_EXTENSION}


async def materialize_task_media_handles(
    handles: Sequence[Any], *, execution_substrate: Any, cache_dir: str | Path,
) -> tuple[Any, ...]:
    """Read only selected, sealed task media; private snapshots never change public identity."""
    result = []
    for handle in handles:
        path = str(handle.tool_path or handle.logical_path or "")
        if handle.host_path or not is_model_media_path(path) or execution_substrate is None:
            result.append(handle)
            continue
        provenance = handle.provenance or {}
        digest = str(provenance.get("content_sha256") or "")
        size = provenance.get("byte_size")
        if not digest or type(size) is not int:
            raise ModelMediaProjectionError("model_media_task_identity_missing")
        if size > MAX_MODEL_MEDIA_BYTES:
            raise ModelMediaProjectionError("model_media_size_limit_exceeded")
        destination = Path(cache_dir) / (digest + Path(path).suffix.lower())
        if not destination.is_file():
            raw = await execution_substrate.read_bytes(path)
            if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
                raise ModelMediaProjectionError("model_media_task_identity_mismatch")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        result.append(handle.model_copy(update={"host_path": str(destination), "extension": Path(path).suffix.lower()}))
    return tuple(result)


async def build_task_authorized_model_media_parts(request: Any, *, execution_substrate: Any,
                                                cache_dir: str | Path, **kwargs: Any):
    """Use the ordinary sealed projection after acquiring external task bytes."""
    from types import SimpleNamespace
    handles = await materialize_task_media_handles(request.upstream_artifact_handles,
        execution_substrate=execution_substrate, cache_dir=cache_dir)
    return build_authorized_model_media_parts(SimpleNamespace(
        authorized_materials=request.authorized_materials, upstream_artifact_handles=handles), **kwargs)


async def build_controller_observation_media_parts(handles: Sequence[Any], *, execution_substrate: Any,
                                                 cache_dir: str | Path, **kwargs: Any):
    """Project media actually produced by this Controller's sealed Tool calls."""
    from .formal_contracts import MaterialDescriptorV1
    declared = _declared_input_modalities(kwargs["model_manifest"])
    selected = {}
    for handle in handles:
        path = str(handle.tool_path or handle.logical_path or "")
        modality = "image" if Path(path).suffix.lower() in _IMAGE_MIME_BY_EXTENSION else "audio"
        if handle.current_run and is_model_media_path(path) and modality in declared:
            selected[path] = handle
    if not selected:
        return [], []
    resolved = await materialize_task_media_handles(tuple(selected.values()),
        execution_substrate=execution_substrate, cache_dir=cache_dir)
    materials = tuple(MaterialDescriptorV1(source_id="artifact:" + handle.handle_id,
        logical_name=Path(str(handle.tool_path or handle.logical_path)).name,
        artifact_type=handle.artifact_type, content_sha256=handle.provenance["content_sha256"],
        original_bytes=handle.provenance["byte_size"], included_bytes=0,
        coverage_status="handle_only", handle_id=handle.handle_id, runtime_path=handle.tool_path)
        for handle in resolved)
    return build_model_media_parts_from_materials(authorized_materials=materials,
        upstream_artifact_handles=resolved, **kwargs)


def _model_profile(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    typed = manifest.get("type_specific")
    typed = typed if isinstance(typed, Mapping) else {}
    model = typed.get("model")
    return model if isinstance(model, Mapping) else {}


def _declared_input_modalities(manifest: Mapping[str, Any]) -> frozenset[str]:
    return frozenset(
        str(item).strip().lower()
        for item in (_model_profile(manifest).get("input_modalities") or ())
        if str(item).strip()
    )


def _live_capabilities(
    *,
    project_root: str | Path,
    endpoint_identity_sha256: str,
    model_resource_id: str,
    provider_model_id: str,
) -> frozenset[str]:
    state = load_applied_model_ready_state(
        project_root,
        expected_endpoint_identity_sha256=endpoint_identity_sha256,
    )
    record = state.by_resource_id.get(str(model_resource_id))
    if record is None or record.model_id != str(provider_model_id):
        raise ModelMediaProjectionError("model_media_ready_identity_missing")
    return frozenset(record.capabilities_live_verified)


def build_authorized_model_media_parts(
    request: Any,
    *,
    model_manifest: Mapping[str, Any],
    model_resource_id: str,
    provider_model_id: str,
    project_root: str | Path,
    endpoint_identity_sha256: str,
    max_media_bytes: int = MAX_MODEL_MEDIA_BYTES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return provider content parts and redacted audit records.

    UTF-8 materials remain in ``ResourceCallRequest.model_visible_payload``.
    Only handle-only image/audio materials are projected here.  Other binary
    formats must be transformed by a selected deterministic Tool or another
    explicitly compiled step.
    """

    return build_model_media_parts_from_materials(
        authorized_materials=request.authorized_materials,
        upstream_artifact_handles=request.upstream_artifact_handles,
        model_manifest=model_manifest,
        model_resource_id=model_resource_id,
        provider_model_id=provider_model_id,
        project_root=project_root,
        endpoint_identity_sha256=endpoint_identity_sha256,
        max_media_bytes=max_media_bytes,
    )


def build_model_media_parts_from_materials(
    *,
    authorized_materials: Sequence[Any],
    upstream_artifact_handles: Sequence[Any],
    model_manifest: Mapping[str, Any],
    model_resource_id: str,
    provider_model_id: str,
    project_root: str | Path,
    endpoint_identity_sha256: str,
    max_media_bytes: int = MAX_MODEL_MEDIA_BYTES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Project an already sealed descriptor/handle set for any model kernel."""

    descriptors = {
        str(item.handle_id): item
        for item in authorized_materials
        if item.handle_id is not None
    }
    handles = {
        str(item.handle_id): item for item in upstream_artifact_handles
    }
    if set(descriptors) != set(handles):
        raise ModelMediaProjectionError("model_media_handle_set_mismatch")

    binary_pairs: list[tuple[Any, Any, str, str]] = []
    required_modalities: set[str] = set()
    for handle_id in sorted(descriptors):
        descriptor = descriptors[handle_id]
        if descriptor.coverage_status != "handle_only":
            continue
        handle = handles[handle_id]
        extension = str(handle.extension or "").strip().lower()
        if not extension:
            extension = Path(str(handle.logical_path or "")).suffix.lower()
        if extension in _IMAGE_MIME_BY_EXTENSION:
            modality = "image"
            capability = "vision"
        elif extension in _AUDIO_FORMAT_BY_EXTENSION:
            modality = "audio"
            capability = "audio_input"
        else:
            raise ModelMediaProjectionError(
                "model_binary_material_requires_compiled_adapter"
            )
        required_modalities.add(modality)
        binary_pairs.append((descriptor, handle, modality, capability))

    if not binary_pairs:
        return [], []

    declared_modalities = _declared_input_modalities(model_manifest)
    missing_declared = sorted(required_modalities - declared_modalities)
    if missing_declared:
        raise ModelMediaProjectionError(
            "model_media_modality_not_declared:" + ",".join(missing_declared)
        )
    live = _live_capabilities(
        project_root=project_root,
        endpoint_identity_sha256=endpoint_identity_sha256,
        model_resource_id=model_resource_id,
        provider_model_id=provider_model_id,
    )

    parts: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for descriptor, handle, modality, capability in binary_pairs:
        if capability not in live:
            raise ModelMediaProjectionError(
                f"model_media_capability_not_live_verified:{capability}"
            )
        host_path = str(handle.host_path or "")
        if not host_path:
            raise ModelMediaProjectionError("model_media_host_material_missing")
        source = Path(host_path)
        if not source.is_file():
            raise ModelMediaProjectionError("model_media_host_material_unreadable")
        try:
            raw = source.read_bytes()
        except OSError as exc:
            raise ModelMediaProjectionError(
                "model_media_host_material_unreadable"
            ) from exc
        if len(raw) > int(max_media_bytes):
            raise ModelMediaProjectionError("model_media_size_limit_exceeded")
        digest = hashlib.sha256(raw).hexdigest()
        if len(raw) != int(descriptor.original_bytes):
            raise ModelMediaProjectionError("model_media_descriptor_size_mismatch")
        if digest != str(descriptor.content_sha256):
            raise ModelMediaProjectionError("model_media_descriptor_hash_mismatch")

        encoded = base64.b64encode(raw).decode("ascii")
        extension = str(handle.extension or "").strip().lower()
        if not extension:
            extension = Path(str(handle.logical_path or "")).suffix.lower()
        if modality == "image":
            mime = _IMAGE_MIME_BY_EXTENSION[extension]
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime};base64,{encoded}",
                        "detail": "auto",
                    },
                }
            )
        else:
            audio_format = _AUDIO_FORMAT_BY_EXTENSION[extension]
            parts.append(
                {
                    "type": "input_audio",
                    "input_audio": {"data": encoded, "format": audio_format},
                }
            )
        audit.append(
            {
                "source_id": str(descriptor.source_id),
                "handle_id": str(descriptor.handle_id),
                "modality": modality,
                "content_sha256": digest,
                "byte_size": len(raw),
                "capability_evidence": capability,
            }
        )
    return parts, audit


def compose_model_user_content(
    text_payload: str,
    media_parts: Sequence[Mapping[str, Any]] | None,
) -> str | list[dict[str, Any]]:
    """Preserve the exact text contract and append sealed media parts."""

    if not media_parts:
        return text_payload
    return [
        {"type": "text", "text": text_payload},
        *(dict(item) for item in media_parts),
    ]
