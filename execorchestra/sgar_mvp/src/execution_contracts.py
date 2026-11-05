"""Pure compatibility checks between manifest inputs and runtime artifacts."""

from dataclasses import dataclass
import os
from typing import Any, Mapping, Optional, Tuple

from .schema import ArtifactHandle


_ARTIFACT_TYPE_ALIASES = {
    "c": "code",
    "c_source": "code",
    "cc": "code",
    "cpp": "code",
    "cxx": "code",
    "c_header": "code",
    "cpp_header": "code",
    "python": "code",
    "javascript": "code",
    "typescript": "code",
    "java": "code",
    "rust": "code",
    "go": "code",
    "ruby": "code",
    "shell": "code",
    "bash": "code",
    "swift": "code",
    "kotlin": "code",
    "csharp": "code",
    "coq_source": "code",
    "text": "plaintext",
    "plain_text": "plaintext",
    "plaintext": "plaintext",
}

_PATH_KIND_ALIASES = {
    "file": "file_path",
    "filepath": "file_path",
    "file_path": "file_path",
    "directory": "directory_path",
    "directorypath": "directory_path",
    "directory_path": "directory_path",
    "dir": "directory_path",
    "dir_path": "directory_path",
    "path": "path",
}

_PATH_KINDS = frozenset({"file_path", "directory_path", "path"})

# Machine-readable input kinds currently understood by the generic binder and
# executors.  Descriptive prose belongs in manifest descriptions, not here.
_KNOWN_INPUT_KINDS = frozenset(
    {
        "value",
        "string",
        "str",
        "list",
        "number",
        "integer",
        "boolean",
        "object",
        "json",
        *_PATH_KINDS,
    }
)

_EXTENSION_ARTIFACT_TYPES = {
    ".c": "code",
    ".cc": "code",
    ".cpp": "code",
    ".cxx": "code",
    ".h": "code",
    ".hh": "code",
    ".hpp": "code",
    ".hxx": "code",
    ".cs": "code",
    ".csv": "csv",
    ".go": "code",
    ".java": "code",
    ".js": "code",
    ".jsx": "code",
    ".json": "json",
    ".kt": "code",
    ".kts": "code",
    ".md": "markdown",
    ".markdown": "markdown",
    ".pdf": "pdf",
    ".tex": "code",
    ".py": "code",
    ".rb": "code",
    ".rs": "code",
    ".sh": "code",
    ".swift": "code",
    ".ts": "code",
    ".tsx": "code",
    ".v": "code",
    ".vo": "file",
    ".sql": "sql",
    ".text": "plaintext",
    ".txt": "plaintext",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
}


@dataclass(frozen=True)
class NormalizedInputContract:
    """Canonical subset of a Tool manifest input contract used at runtime."""

    name: str = ""
    kind: str = "value"
    artifact_types: Tuple[str, ...] = ()
    extensions: Tuple[str, ...] = ()
    required: bool = True


@dataclass(frozen=True)
class ContractMatch:
    """Deterministic result of comparing one value with one input contract."""

    compatible: bool
    failure_type: Optional[str] = None
    reason: str = ""


def _normalized_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def normalize_artifact_type(value: Any) -> str:
    """Return the system-wide canonical semantic artifact type."""
    token = _normalized_token(value)
    return _ARTIFACT_TYPE_ALIASES.get(token, token)


def _as_values(value: Any) -> Tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(value)
    return (value,)


def _unique(values: Tuple[str, ...]) -> Tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _normalize_extension(value: Any) -> str:
    extension = str(value or "").strip().lower()
    if extension and not extension.startswith("."):
        extension = f".{extension}"
    return extension


def normalize_input_contract(raw_contract: Any) -> NormalizedInputContract:
    """Normalize legacy scalar and structured manifest input declarations."""

    if isinstance(raw_contract, NormalizedInputContract):
        raw: Mapping[str, Any] = {
            "name": raw_contract.name,
            "kind": raw_contract.kind,
            "artifact_types": raw_contract.artifact_types,
            "extensions": raw_contract.extensions,
            "required": raw_contract.required,
        }
    elif isinstance(raw_contract, str):
        raw: Mapping[str, Any] = {"kind": raw_contract}
    elif isinstance(raw_contract, Mapping):
        raw = raw_contract
    else:
        raw = {"kind": "value"}

    raw_kind = _normalized_token(raw.get("kind") or "value")
    kind = _PATH_KIND_ALIASES.get(raw_kind, raw_kind)
    artifact_types = _unique(
        tuple(normalize_artifact_type(item) for item in _as_values(raw.get("artifact_types")))
    )
    if not artifact_types and raw.get("artifact_type") is not None:
        artifact_types = _unique((normalize_artifact_type(raw.get("artifact_type")),))
    extensions = _unique(
        tuple(_normalize_extension(item) for item in _as_values(raw.get("extensions")))
    )
    if not extensions and raw.get("extension") is not None:
        extensions = _unique((_normalize_extension(raw.get("extension")),))

    return NormalizedInputContract(
        name=str(raw.get("name") or "").strip(),
        kind=kind,
        artifact_types=artifact_types,
        extensions=extensions,
        required=bool(raw.get("required", True)),
    )


def _contract_entries(value: Any) -> Tuple[Any, ...]:
    """Return a uniform view while preserving legacy scalar declarations."""
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(value)
    return (value,)


def _validate_string_list(value: Any, field: str, errors: list[str]) -> Tuple[str, ...]:
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return ()
    result = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}[{index}] must be a non-empty string")
        else:
            result.append(item.strip())
    return tuple(result)


def validate_tool_execution_contract(manifest: Any) -> tuple[bool, tuple[str, ...]]:
    """Validate Tool execution contracts without guessing or filesystem I/O.

    Root-level contracts and ``io`` mirrors are accepted for compatibility,
    but when both are present they must be identical.  This makes one loaded
    Tool expose one deterministic contract to routing, binding and execution.
    """
    if not isinstance(manifest, Mapping):
        return False, ("manifest must be an object",)

    errors: list[str] = []
    io = manifest.get("io")
    if io is not None and not isinstance(io, Mapping):
        errors.append("io must be an object")
        io = {}
    io = io or {}

    root_input = manifest.get("input_contract")
    io_input = io.get("input_contract")
    if root_input is not None and io_input is not None and root_input != io_input:
        errors.append("root/io input_contract mismatch")
    input_contract = root_input if root_input is not None else io_input

    if input_contract is not None and not isinstance(input_contract, (str, list)):
        errors.append("input_contract must be a scalar string or list")
        input_contract = []

    for index, raw in enumerate(_contract_entries(input_contract)):
        location = f"input_contract[{index}]"
        if isinstance(raw, str):
            kind = _PATH_KIND_ALIASES.get(_normalized_token(raw), _normalized_token(raw))
        elif isinstance(raw, Mapping):
            raw_kind = raw.get("kind", "value")
            kind = _PATH_KIND_ALIASES.get(_normalized_token(raw_kind), _normalized_token(raw_kind))
            if "extensions" in raw:
                extensions = _validate_string_list(raw.get("extensions"), f"{location}.extensions", errors)
                for extension in extensions:
                    if not extension.startswith("."):
                        errors.append(f"{location}.extensions value {extension!r} must start with '.'")
                    elif len(extension) == 1:
                        errors.append(f"{location}.extensions value {extension!r} must contain a valid suffix")
            if "artifact_types" in raw:
                _validate_string_list(raw.get("artifact_types"), f"{location}.artifact_types", errors)
        else:
            errors.append(f"{location} must be a string or object")
            continue
        if kind not in _KNOWN_INPUT_KINDS:
            errors.append(f"{location} has unknown input kind {kind!r}")

    root_output = manifest.get("output_contract")
    io_output = io.get("output_contract")
    if root_output is not None and io_output is not None and root_output != io_output:
        errors.append("root/io output_contract mismatch")
    output_contract = root_output if root_output is not None else io_output

    transport_type = ""
    semantic_type = ""
    if output_contract is not None:
        if isinstance(output_contract, str):
            if not output_contract.strip():
                errors.append("output_contract.artifact_type must be a non-empty string")
            else:
                transport_type = normalize_artifact_type(output_contract)
        elif isinstance(output_contract, Mapping):
            raw_transport_type = output_contract.get("artifact_type")
            if not isinstance(raw_transport_type, str) or not raw_transport_type.strip():
                errors.append("output_contract.artifact_type must be a non-empty string")
            else:
                transport_type = normalize_artifact_type(raw_transport_type)
            semantic = output_contract.get("semantic_output")
            if semantic is not None:
                if not isinstance(semantic, Mapping):
                    errors.append("output_contract.semantic_output must be an object")
                else:
                    raw_semantic_type = semantic.get("artifact_type")
                    if not isinstance(raw_semantic_type, str) or not raw_semantic_type.strip():
                        errors.append("output_contract.semantic_output.artifact_type must be a non-empty string")
                    else:
                        semantic_type = normalize_artifact_type(raw_semantic_type)
                    payload_path = semantic.get("payload_path")
                    if not isinstance(payload_path, str) or not payload_path.strip():
                        errors.append("output_contract.semantic_output.payload_path must be a non-empty string")
                    if transport_type != "json":
                        errors.append("output_contract.semantic_output requires JSON transport")
            result_status = output_contract.get("result_status")
            if result_status is not None:
                if not isinstance(result_status, Mapping):
                    errors.append("output_contract.result_status must be an object")
                else:
                    status_path = result_status.get("payload_path")
                    if not isinstance(status_path, str) or not status_path.strip():
                        errors.append(
                            "output_contract.result_status.payload_path must be a non-empty string"
                        )
                    success_values = _validate_string_list(
                        result_status.get("success_values"),
                        "output_contract.result_status.success_values",
                        errors,
                    )
                    failure_values = _validate_string_list(
                        result_status.get("failure_values"),
                        "output_contract.result_status.failure_values",
                        errors,
                    )
                    if set(success_values).intersection(failure_values):
                        errors.append(
                            "output_contract.result_status success/failure values must be disjoint"
                        )
                    if transport_type != "json":
                        errors.append("output_contract.result_status requires JSON transport")
        else:
            errors.append("output_contract must be a string or object")

    constraint = manifest.get("constraint") or {}
    if not isinstance(constraint, Mapping):
        errors.append("constraint must be an object")
    elif "artifact_output" in constraint:
        declared = _validate_string_list(
            constraint.get("artifact_output"), "constraint.artifact_output", errors
        )
        declared_types = {normalize_artifact_type(item) for item in declared}
        expected_types = {item for item in (transport_type, semantic_type) if item}
        # ``artifact_output`` describes the complete set of artifacts a Tool
        # may materialize, while ``output_contract.artifact_type`` describes
        # the transport value returned to the planner.  A JSON receipt may
        # therefore legitimately reference additional WARC/WACZ (or similar)
        # side artifacts.  Require the transport/semantic types to be present
        # but allow those explicitly declared side-artifact types as well.
        if expected_types and not expected_types.issubset(declared_types):
            errors.append(
                "constraint.artifact_output must include declared output types "
                f"{sorted(expected_types)!r}"
            )

    return not errors, tuple(errors)


def infer_artifact_type_from_path(path: Any, default: str = "plaintext") -> str:
    """Infer a semantic artifact type from a filename extension."""

    extension = os.path.splitext(str(path or ""))[1].lower()
    return _EXTENSION_ARTIFACT_TYPES.get(extension, normalize_artifact_type(default))


def _mismatch(reason: str) -> ContractMatch:
    return ContractMatch(
        compatible=False,
        failure_type="tool_input_contract_mismatch",
        reason=reason,
    )


def _handle_path_kind(handle: ArtifactHandle) -> str:
    token = _normalized_token(handle.path_kind)
    normalized = _PATH_KIND_ALIASES.get(token, token)
    if normalized == "file_path":
        return "file"
    if normalized == "directory_path":
        return "directory"
    return normalized


def _handle_extension(handle: ArtifactHandle) -> str:
    if handle.extension:
        return _normalize_extension(handle.extension)
    for path in (handle.host_path, handle.logical_path, handle.tool_path):
        extension = os.path.splitext(str(path or ""))[1]
        if extension:
            return _normalize_extension(extension)
    return ""


def match_artifact_handle(contract: Any, handle: Any) -> ContractMatch:
    """Match all explicitly declared compatibility dimensions, without I/O."""

    normalized = normalize_input_contract(contract)
    is_path_contract = normalized.kind in _PATH_KINDS
    if not is_path_contract and normalized.kind.endswith("path"):
        return _mismatch(f"Unknown declared path kind: {normalized.kind}")
    if handle is None and not normalized.required:
        return ContractMatch(compatible=True)

    if not isinstance(handle, ArtifactHandle):
        if is_path_contract:
            return _mismatch(
                f"Input {normalized.name or '<unnamed>'} requires an artifact path handle"
            )
        if normalized.required and handle is None:
            return _mismatch(f"Required input {normalized.name or '<unnamed>'} is missing")
        if normalized.artifact_types or normalized.extensions:
            return _mismatch("Plain values do not expose declared artifact compatibility metadata")
        return ContractMatch(compatible=True)

    if is_path_contract:
        actual_path_kind = _handle_path_kind(handle)
        expected_path_kinds = {
            "file_path": {"file"},
            "directory_path": {"directory"},
            "path": {"file", "directory", "path"},
        }[normalized.kind]
        if actual_path_kind not in expected_path_kinds:
            return _mismatch(
                f"Handle path kind {actual_path_kind or '<unknown>'} does not match {normalized.kind}"
            )
        if normalized.required and handle.exists is not True:
            return _mismatch("Required artifact path does not have confirmed existence")

    generic_directory = normalized.kind == "path" and _handle_path_kind(handle) == "directory"

    if normalized.artifact_types and not generic_directory:
        actual_artifact_type = normalize_artifact_type(handle.artifact_type)
        if actual_artifact_type not in normalized.artifact_types:
            return _mismatch(
                f"Handle artifact type {actual_artifact_type or '<unknown>'} is not one of "
                f"{list(normalized.artifact_types)}"
            )

    if normalized.extensions and not generic_directory:
        actual_extension = _handle_extension(handle)
        if actual_extension not in normalized.extensions:
            return _mismatch(
                f"Handle extension {actual_extension or '<none>'} is not one of "
                f"{list(normalized.extensions)}"
            )

    return ContractMatch(compatible=True)
