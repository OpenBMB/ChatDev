"""Case-agnostic binding and manifest contract semantics.

This module deliberately has no dependency on experiment suites, manifests, or
validators.  It defines the small, shared grammar used by routing, preflight,
execution, and experiment analysis so that a binding cannot change meaning
between those stages.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

from .path_namespace import PathNamespaceError
from .path_policy import assert_linux_control_path


BINDING_PROTOCOL = "binding-protocol-v3"


class BindingProtocolError(ValueError):
    """A binding object is ambiguous or violates the shared source grammar."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class BindingFrameworkError(BindingProtocolError):
    """A registered framework source violated the active path namespace."""


_SOURCE_ALIASES = {
    "literal": ("literal", "value", "source"),
    "path": ("path", "file_path"),
    "artifact_handle": ("artifact_handle", "handle_id"),
    "resource": ("resource_id", "from_resource", "resource"),
    "step_output": (
        "from_step",
        "step_id",
        "output_key",
        "from_output",
        "artifact_key",
        "context_key",
    ),
}
_SOURCE_KEYS = frozenset(
    key for aliases in _SOURCE_ALIASES.values() for key in aliases
)


@dataclass(frozen=True)
class BindingSource:
    """One parsed binding source.

    ``literal`` values are intentionally opaque.  No nested key inside a
    literal is ever interpreted as dependency metadata.
    """

    variant: str
    value: Any = None
    from_step: Optional[str] = None
    output_key: Optional[str] = None
    value_path: Optional[tuple[str, ...]] = None


def canonical_json(value: Any) -> str:
    """Serialize a structured or falsey literal deterministically."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def stringify_literal(value: Any) -> str:
    """Preserve strings and canonically serialize every other literal type."""

    if isinstance(value, str):
        return value
    return canonical_json(value)


def normalize_contract_kind(contract: Mapping[str, Any]) -> str:
    """Normalize one input contract without overriding an explicit kind.

    Name-based inference is used only when ``kind`` is absent or blank.  A
    generic ``*_path`` name means any existing path, never file-only.
    """

    name = str(contract.get("name") or "").strip().lower()
    raw_kind = contract.get("kind")
    kind = str(raw_kind).strip().lower() if raw_kind is not None else ""

    aliases = {
        "file_path": "file_path",
        "file": "file_path",
        "filepath": "file_path",
        "file-path": "file_path",
        "directory_path": "directory_path",
        "directory": "directory_path",
        "dir": "directory_path",
        "dir_path": "directory_path",
        "directory-path": "directory_path",
        "path": "path",
        "any_path": "path",
        "filesystem_path": "path",
        "generic_path": "path",
        "int": "int",
        "integer": "int",
        "float": "float",
        "number": "float",
        "decimal": "float",
        "bool": "bool",
        "boolean": "bool",
        "str": "text",
        "string": "text",
        "text": "text",
        "plaintext": "text",
        "list": "list",
        "array": "list",
        "sequence": "list",
        "object": "object",
        "mapping": "object",
        "dict": "object",
        "json": "json",
    }
    if kind:
        return aliases.get(kind, kind)

    # A name ending in ``_path`` conveys path-ness only.  File-vs-directory
    # constraints require an explicit manifest kind; guessing either would
    # override the manifest's actual contract at another framework layer.
    if name == "path" or name.endswith("_path"):
        return "path"
    if name in {"file", "input_file", "output_file", "source_file"} or name.endswith("_file"):
        return "file_path"
    if name in {"directory", "dir", "cwd", "working_directory"} or name.endswith(("_dir", "_directory")):
        return "directory_path"
    return "text"


def artifact_handle_matches_input_contract(descriptor: Any, contract: Mapping[str, Any]) -> bool:
    """The existing lowering rule, shared with the Compiler's advertised bindings."""
    kind = normalize_contract_kind(contract)
    artifact_type = str(getattr(descriptor, "artifact_type", "") or "").lower()
    if kind == "file_path":
        return artifact_type != "directory"
    if kind == "directory_path":
        return artifact_type == "directory"
    if kind == "json":
        return artifact_type == "json"
    if kind == "list" and contract.get("accepts_artifact_handle_item") is True:
        return artifact_type == "directory" or getattr(descriptor, "size", None) is not None
    return kind in {"artifact", "artifact_ref", "evidence_bundle", "file_path", "path", "text"}


def _one_alias_value(binding: Mapping[str, Any], aliases: Sequence[str], variant: str) -> Any:
    present = [(key, binding[key]) for key in aliases if key in binding]
    if not present:
        return None
    first = present[0][1]
    if any(
        type(value) is not type(first) or value != first
        for _, value in present[1:]
    ):
        keys = ", ".join(key for key, _ in present)
        raise BindingProtocolError(
            "binding_conflicting_aliases",
            f"Binding has conflicting aliases for {variant}: {keys}.",
        )
    return first


def parse_binding_source(binding: Any) -> BindingSource:
    """Parse a scalar binding into exactly one source variant.

    A mapping with no reserved source keys is an opaque structured literal.
    A list is also a literal here; callers handling a list-valued contract may
    explicitly parse its elements as an ordered argument sequence.
    """

    if not isinstance(binding, Mapping):
        return BindingSource("literal", deepcopy(binding))

    variants = [
        variant
        for variant, aliases in _SOURCE_ALIASES.items()
        if any(key in binding for key in aliases)
    ]
    if not variants:
        return BindingSource("literal", deepcopy(dict(binding)))
    if len(variants) != 1:
        raise BindingProtocolError(
            "binding_multiple_sources",
            "Binding declares multiple source variants: " + ", ".join(sorted(variants)) + ".",
        )

    variant = variants[0]
    value_path = binding.get("value_path")
    if value_path is not None:
        if variant != "step_output" or not isinstance(value_path, (list, tuple)) or not value_path or not all(isinstance(v, str) for v in value_path):
            raise BindingProtocolError("binding_value_path_invalid", "value_path requires a nonempty list of exact JSON keys on step_output.")
        value_path = tuple(value_path)
    if variant == "step_output":
        step = _one_alias_value(binding, ("from_step", "step_id"), variant)
        output = _one_alias_value(
            binding,
            ("output_key", "from_output", "artifact_key", "context_key"),
            variant,
        )
        if step is None and output is None:
            raise BindingProtocolError(
                "binding_missing_source_value",
                "Step-output binding has neither from_step nor output_key.",
            )
        return BindingSource(
            variant,
            from_step=None if step is None else str(step),
            output_key=None if output is None else str(output),
            value_path=value_path,
        )

    value = _one_alias_value(binding, _SOURCE_ALIASES[variant], variant)
    return BindingSource(variant, deepcopy(value))


def normalize_step_reference(binding: Any, step_to_output: Mapping[str, str]) -> Any:
    """Return a normalized copy of one binding without touching opaque data."""

    if isinstance(binding, (list, tuple)):
        return [normalize_step_reference(item, step_to_output) for item in binding]
    source = parse_binding_source(binding)
    if source.variant != "step_output" or not isinstance(binding, Mapping):
        return deepcopy(binding)
    normalized = deepcopy(dict(binding))
    if source.from_step and not source.output_key and source.from_step in step_to_output:
        normalized["output_key"] = step_to_output[source.from_step]
    return normalized


def dependency_references(binding: Any) -> tuple[set[str], set[str]]:
    """Return explicit upstream step IDs and output keys from one binding."""

    steps: set[str] = set()
    outputs: set[str] = set()
    if isinstance(binding, (list, tuple)):
        for item in binding:
            item_steps, item_outputs = dependency_references(item)
            steps.update(item_steps)
            outputs.update(item_outputs)
        return steps, outputs

    source = parse_binding_source(binding)
    if source.variant == "step_output":
        if source.from_step:
            steps.add(source.from_step)
        if source.output_key:
            outputs.add(source.output_key)
    return steps, outputs


def container_dependency_references(bindings: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    """Return dependencies across a named ``input_bindings`` container."""

    steps: set[str] = set()
    outputs: set[str] = set()
    for binding in bindings.values():
        item_steps, item_outputs = dependency_references(binding)
        steps.update(item_steps)
        outputs.update(item_outputs)
    return steps, outputs


def binding_references_any(
    binding: Any,
    *,
    producer_step_ids: Iterable[str] = (),
    output_keys: Iterable[str] = (),
) -> bool:
    """Whether a binding explicitly references one of the supplied producers."""

    producer_set = {str(item) for item in producer_step_ids}
    output_set = {str(item) for item in output_keys}
    steps, outputs = dependency_references(binding)
    if steps & producer_set or outputs & output_set:
        return True
    # Preserve the legacy shorthand only for scalar strings.  Strings nested in
    # opaque JSON objects are data and are intentionally not traversed.
    return isinstance(binding, str) and binding in (producer_set | output_set)


def source_keys() -> frozenset[str]:
    """Expose reserved keys for schema/audit tests without mutable state."""

    return _SOURCE_KEYS


def _mapping_or_attribute(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _indexed_handles(handles: Mapping[str, Any] | Sequence[Any]) -> dict[str, Any]:
    """Normalize an ArtifactHandle sequence or an already indexed registry.

    The binding protocol intentionally does not import the application's schema
    module.  Keeping this adapter structural makes the resolver reusable in the
    Router, preflight, execution, and offline analysis without introducing a
    dependency on any experiment suite.
    """

    if isinstance(handles, Mapping):
        return {str(key): value for key, value in handles.items()}
    indexed: dict[str, Any] = {}
    for handle in handles:
        handle_id = _mapping_or_attribute(handle, "handle_id")
        if handle_id is not None:
            indexed[str(handle_id)] = handle
    return indexed


def _handle_binding_value(handle: Any) -> Any:
    """Return the private execution value of a registered handle.

    Internal execution prefers ``host_path``.  Public/runtime serialization can
    supply a ``path_mapper`` to replace it recursively before the result crosses
    the framework boundary.  Plain values in a mapping are also supported so
    callers can expose non-artifact sources (for example a resource URI) through
    the same resolver without teaching this module about manifests.
    """

    for key in ("host_path", "tool_path", "logical_path", "value"):
        value = _mapping_or_attribute(handle, key)
        if value is not None:
            return deepcopy(value)
    if isinstance(handle, Mapping):
        execution = handle.get("execution")
        if isinstance(execution, Mapping) and "uri" in execution:
            return deepcopy(execution["uri"])
    return deepcopy(handle)


def _resolve_one_source(
    source: Any,
    handles: Mapping[str, Any],
    step_outputs: Mapping[str, Any],
) -> Any:
    parsed = parse_binding_source(source)
    if parsed.variant in {"literal", "path"}:
        return deepcopy(parsed.value)

    if parsed.variant in {"artifact_handle", "resource"}:
        source_id = str(parsed.value)
        handle = handles.get(source_id)
        if handle is None and parsed.variant == "artifact_handle" and source_id.startswith(
            "artifact:"
        ):
            handle = handles.get(source_id.removeprefix("artifact:"))
        if handle is None:
            code = (
                "artifact_handle_missing"
                if parsed.variant == "artifact_handle"
                else "binding_resource_missing"
            )
            raise BindingProtocolError(
                code,
                f"Binding source {source_id!r} is not registered.",
            )
        return _handle_binding_value(handle)

    # A step-output binding may carry both fields.  output_key is the stable
    # data-plane identity; from_step remains a compatibility fallback.
    for key in (parsed.output_key, parsed.from_step):
        if key is not None and str(key) in step_outputs:
            value = deepcopy(step_outputs[str(key)])
            return select_binding_value(value, parsed.value_path) if parsed.value_path is not None else value
    requested = parsed.output_key or parsed.from_step or "<missing>"
    raise BindingProtocolError(
        "binding_step_output_missing",
        f"Step-output source {requested!r} is not available.",
    )


def _map_nested_paths(value: Any, path_mapper: Optional[Callable[[str], str]]) -> Any:
    if path_mapper is None:
        return deepcopy(value)
    if isinstance(value, str):
        return path_mapper(value)
    if isinstance(value, Mapping):
        return {
            str(key): _map_nested_paths(item, path_mapper)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_map_nested_paths(item, path_mapper) for item in value]
    return deepcopy(value)


def _atomic_argument(
    value: Any,
    path_mapper: Optional[Callable[[str], str]],
    *,
    map_scalar_path: bool = True,
) -> str:
    # A scalar string under an explicit text contract is opaque data.  It must
    # not be reinterpreted merely because it happens to equal an absolute host
    # path.  Structured values and typed path/list contracts still map exact
    # registered path leaves before their one-time canonical serialization.
    mapped = (
        deepcopy(value)
        if isinstance(value, str) and not map_scalar_path
        else _map_nested_paths(value, path_mapper)
    )
    try:
        return stringify_literal(mapped)
    except (TypeError, ValueError) as exc:
        raise BindingProtocolError(
            "binding_serialization_failed",
            f"Binding value is not canonical-JSON serializable: {exc}",
        ) from exc


def _list_source_items(source: Any) -> list[Any]:
    """Expose only the list contract's outer sequence as argv positions."""

    parsed = parse_binding_source(source)
    if parsed.variant == "literal" and isinstance(parsed.value, (list, tuple)):
        return list(parsed.value)
    if not isinstance(source, Mapping) and isinstance(source, (list, tuple)):
        return list(source)
    return [source]


def _explicit_literal_source(source: Any, parsed: BindingSource) -> bool:
    return bool(
        parsed.variant == "literal"
        and isinstance(source, Mapping)
        and any(key in source for key in _SOURCE_ALIASES["literal"])
    )


def resolve_binding(
    source: Any,
    contract: Mapping[str, Any],
    handles: Mapping[str, Any] | Sequence[Any],
    step_outputs: Mapping[str, Any],
    path_mapper: Optional[Callable[[str], str]] = None,
) -> str | list[str]:
    """Resolve one binding under the shared typed contract.

    The return is immediately argv-safe: scalar structured values use
    canonical JSON, while a ``list`` contract returns one string per *outer*
    element.  Nested lists and dictionaries remain one atomic argument.  A
    mapper, when supplied, is applied recursively before JSON serialization so
    host paths cannot hide inside structured argv values.

    Presence is structural rather than truthy: ``0``, ``False``, ``""``, an
    empty list, and explicit ``None`` all resolve normally.
    """

    handle_index = _indexed_handles(handles)
    kind = normalize_contract_kind(contract)

    if kind in {"path", "file_path", "directory_path"}:
        # This check is applied to declared control-plane path bindings only;
        # literal text contracts are intentionally opaque task data.
        parsed_for_path = parse_binding_source(source)
        if parsed_for_path.variant in {"literal", "path"} and isinstance(
            parsed_for_path.value, str
        ):
            try:
                assert_linux_control_path(
                    parsed_for_path.value,
                    field_name=str(contract.get("name") or "path"),
                )
            except ValueError as exc:
                raise BindingProtocolError(
                    "binding_non_posix_control_path", str(exc)
                ) from exc

    def atomic(value: Any, parsed: BindingSource, *, map_paths: bool) -> str:
        try:
            return _atomic_argument(
                value,
                path_mapper if map_paths else None,
                map_scalar_path=map_paths,
            )
        except PathNamespaceError as exc:
            if parsed.variant in {"artifact_handle", "resource", "step_output"}:
                raise BindingFrameworkError(
                    "registered_binding_path_unmappable",
                    "A registered binding source is not represented by the active sandbox scope.",
                ) from exc
            raise BindingProtocolError(
                "binding_path_out_of_scope",
                "A Plan-supplied binding path is outside the active sandbox scope.",
            ) from exc

    if kind == "list":
        resolved_items: list[str] = []
        for item in _list_source_items(source):
            parsed_item = parse_binding_source(item)
            resolved = _resolve_one_source(item, handle_index, step_outputs)
            # If a referenced source itself yields a list, it is structured data
            # for this argv position; only the binding's outer list expands.
            resolved_items.append(
                atomic(
                    resolved,
                    parsed_item,
                    map_paths=not _explicit_literal_source(item, parsed_item),
                )
            )
        return resolved_items

    # Structured literals remain intact for scalar contracts and are emitted as
    # one canonical JSON argument.  Silently selecting the first list element
    # changes data and makes preflight disagree with execution.
    parsed_source = parse_binding_source(source)
    value = _resolve_one_source(source, handle_index, step_outputs)
    return atomic(
        value,
        parsed_source,
        map_paths=(
            not _explicit_literal_source(source, parsed_source)
            and (
                kind in {"path", "file_path", "directory_path"}
                or parsed_source.variant
                in {"path", "artifact_handle", "resource", "step_output"}
                or not isinstance(value, str)
            )
        ),
    )


def select_binding_value(value: Any, path: Sequence[str]) -> Any:
    """Extract the Compiler-selected JSON value; never guess a payload field."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise BindingProtocolError("binding_value_not_json", "Selected source is not JSON.") from exc
    for key in path:
        if isinstance(value, Mapping) and key in value:
            value = value[key]
        elif isinstance(value, list) and key.isdigit() and str(int(key)) == key and int(key) < len(value):
            value = value[int(key)]
        else:
            raise BindingProtocolError("binding_value_path_missing", "The explicitly selected result field is absent.")
    return deepcopy(value)


def selected_value_schema(schema: Mapping[str, Any], path: Sequence[str]) -> Mapping[str, Any]:
    """Resolve exact properties/items through local refs and schema alternatives.

    A field can exist only in a success alternative. Runtime absence remains a
    binding failure; this does not claim every variant produces that field.
    """
    root = schema
    def expand(node, seen=()):
        if not isinstance(node, Mapping):
            return []
        ref = node.get("$ref")
        if ref is not None:
            if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
                return []
            target = root
            for token in ref[2:].split("/"):
                target = target.get(token.replace("~1", "/").replace("~0", "~"), {}) if isinstance(target, Mapping) else {}
            return expand(target, (*seen, ref))
        variants = node.get("oneOf", node.get("anyOf"))
        if isinstance(variants, list):
            return [leaf for variant in variants for leaf in expand(variant, seen)]
        return [node]
    nodes = expand(root)
    for key in path:
        selected = []
        for node in nodes:
            properties = node.get("properties", {})
            if isinstance(properties, Mapping) and key in properties:
                selected.extend(expand(properties[key]))
            elif node.get("type") == "array" and key.isdigit() and str(int(key)) == key:
                prefix = node.get("prefixItems", [])
                selected.extend(expand(prefix[int(key)] if int(key) < len(prefix) else node.get("items")))
        nodes = selected
        if not nodes:
            raise BindingProtocolError("binding_value_path_schema_unproven", "Select a field declared by the producer schema or add an explicit transformation.")
    unique = {canonical_json(node): node for node in nodes}
    return deepcopy(next(iter(unique.values()))) if len(unique) == 1 else {"anyOf": list(unique.values())}


def selected_schema_types(schema: Mapping[str, Any]) -> set[str]:
    variants = schema.get("oneOf", schema.get("anyOf"))
    if isinstance(variants, list):
        return set().union(*(selected_schema_types(v) for v in variants))
    value = schema.get("type")
    if isinstance(value, str):
        return {value}
    return set(value) if isinstance(value, list) else set()
