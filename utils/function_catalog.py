"""Utility helpers for introspecting function-calling tools."""

import inspect
from collections import abc
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Dict, List, Literal, Mapping, Sequence, Tuple, Union, get_args, get_origin

from utils.function_manager import FUNCTION_CALLING_DIR, get_function_manager


@dataclass(frozen=True)
class ParamMeta:
    """Declarative metadata for Annotated parameters."""

    description: str | None = None
    enum: Sequence[Any] | None = None


@dataclass(frozen=True)
class FunctionMetadata:
    """Normalized metadata for a Python callable."""

    name: str
    description: str | None
    parameters_schema: Dict[str, Any]
    module: str
    file_path: str
    module_name: str


class FunctionCatalog:
    """Inspect and cache callable metadata for tool schemas."""

    def __init__(self, functions_dir: str | Path = FUNCTION_CALLING_DIR) -> None:
        self._functions_dir = Path(functions_dir).resolve()
        self._metadata: Dict[str, FunctionMetadata] = {}
        self._loaded = False
        self._load_error: Exception | None = None
        self._module_index: Dict[str, List[str]] = {}

    def refresh(self) -> None:
        """Reload metadata from the function directory."""
        self._metadata.clear()
        self._module_index = {}
        self._load_error = None
        manager = get_function_manager(self._functions_dir)
        try:
            manager.load_functions()
        except Exception as exc:  # pragma: no cover - propagated via catalog usage
            self._loaded = True
            self._load_error = exc
            return

        module_index: Dict[str, List[str]] = {}
        for name, fn in manager.list_functions().items():
            try:
                metadata = _build_function_metadata(name, fn, self._functions_dir)
                self._metadata[name] = metadata
                module_bucket = module_index.setdefault(metadata.module_name, [])
                module_bucket.append(name)
            except Exception as exc:  # pragma: no cover - guarded to avoid cascading failures
                print(f"[FunctionCatalog] Failed to load metadata for {name}: {exc}")
        for module_name, names in module_index.items():
            names.sort()
        self._module_index = module_index
        self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.refresh()

    def get(self, name: str) -> FunctionMetadata | None:
        self._ensure_loaded()
        return self._metadata.get(name)

    def list_function_names(self) -> List[str]:
        self._ensure_loaded()
        return sorted(self._metadata.keys())

    def list_metadata(self) -> Dict[str, FunctionMetadata]:
        self._ensure_loaded()
        return self._metadata.copy()

    def iter_modules(self) -> List[Tuple[str, List[FunctionMetadata]]]:
        """Return functions grouped by Python file (module_name)."""

        self._ensure_loaded()
        modules: List[Tuple[str, List[FunctionMetadata]]] = []
        for module_name in sorted(self._module_index.keys()):
            names = self._module_index.get(module_name, [])
            entries: List[FunctionMetadata] = []
            for fn_name in names:
                meta = self._metadata.get(fn_name)
                if meta is not None:
                    entries.append(meta)
            modules.append((module_name, entries))
        return modules

    def functions_for_module(self, module_name: str) -> List[str]:
        """Return sorted function names for the given module."""

        self._ensure_loaded()
        return list(self._module_index.get(module_name, []))

    @property
    def load_error(self) -> Exception | None:
        self._ensure_loaded()
        return self._load_error


_catalog_registry: Dict[Path, FunctionCatalog] = {}


def get_function_catalog(functions_dir: str | Path = FUNCTION_CALLING_DIR) -> FunctionCatalog:
    directory = Path(functions_dir).resolve()
    catalog = _catalog_registry.get(directory)
    if catalog is None:
        catalog = FunctionCatalog(directory)
        _catalog_registry[directory] = catalog
    return catalog


def _build_function_metadata(name: str, fn: Any, functions_dir: Path) -> FunctionMetadata:
    signature = inspect.signature(fn)
    annotations = _resolve_annotations(fn)

    description = _extract_description(fn)
    schema = _build_parameters_schema(signature, annotations)
    module = getattr(fn, "__module__", "")
    file_path = inspect.getsourcefile(fn) or ""
    module_name = _derive_module_name(file_path, functions_dir)
    return FunctionMetadata(
        name=name,
        description=description,
        parameters_schema=schema,
        module=module,
        file_path=file_path,
        module_name=module_name,
    )


def _derive_module_name(file_path: str, functions_dir: Path) -> str:
    if not file_path:
        return "unknown"
    try:
        relative = Path(file_path).resolve().relative_to(functions_dir.resolve())
        if relative.suffix:
            relative = relative.with_suffix("")
        parts = list(relative.parts)
        if not parts:
            return "unknown"
        return "/".join(parts)
    except Exception:
        stem = Path(file_path).stem
        return stem or "unknown"


def _extract_description(fn: Any) -> str | None:
    doc = inspect.getdoc(fn)
    if not doc:
        return None
    trimmed = doc.strip()
    if not trimmed:
        return None
    first_paragraph = trimmed.split("\n\n", 1)[0]
    normalized_lines = [line.strip() for line in first_paragraph.splitlines() if line.strip()]
    normalized = " ".join(normalized_lines)
    max_len = 600
    if len(normalized) > max_len:
        normalized = normalized[: max_len - 1].rstrip() + "…"
    return normalized or None


def _resolve_annotations(fn: Any) -> Mapping[str, Any]:
    fallback = getattr(fn, "__annotations__", {}) or {}
    get_annotations = getattr(inspect, "get_annotations", None)
    if get_annotations is None:
        return fallback
    try:
        return inspect.get_annotations(fn, eval_str=True, include_extras=True)
    except TypeError:
        try:
            return inspect.get_annotations(fn, eval_str=True)
        except TypeError:
            try:
                return inspect.get_annotations(fn)
            except Exception:
                return fallback
    except Exception:
        return fallback


def _build_parameters_schema(signature: inspect.Signature, annotations: Mapping[str, Any]) -> Dict[str, Any]:
    properties: Dict[str, Any] = {}
    required: List[str] = []

    for param in signature.parameters.values():
        if param.name.startswith("_"):
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        annotation = annotations.get(param.name, inspect._empty)
        annotation, meta = _unwrap_annotation(annotation)
        annotation, optional_from_type = _strip_optional(annotation)
        schema = _annotation_to_schema(annotation)
        schema = _apply_param_meta(schema, meta)

        if param.default is not inspect._empty:
            schema.setdefault("default", param.default)

        properties[param.name] = schema
        is_required = param.default is inspect._empty and not optional_from_type
        if is_required:
            required.append(param.name)

    payload: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        payload["required"] = required
    return payload


def _unwrap_annotation(annotation: Any) -> Tuple[Any, ParamMeta | None]:
    origin = get_origin(annotation)
    if origin is Annotated:
        args = get_args(annotation)
        if not args:
            return annotation, None
        base = args[0]
        meta = next((arg for arg in args[1:] if isinstance(arg, ParamMeta)), None)
        return base, meta
    return annotation, None


def _strip_optional(annotation: Any) -> Tuple[Any, bool]:
    origin = get_origin(annotation)
    if origin is Union:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]  # noqa: E721
        if len(args) == 1 and len(args) != len(get_args(annotation)):
            return args[0], True
    return annotation, False


def _annotation_to_schema(annotation: Any) -> Dict[str, Any]:
    if annotation is inspect._empty or annotation is Any:
        return {"type": "string"}

    origin = get_origin(annotation)
    if origin is None:
        return _primitive_schema(annotation)

    if origin is list or origin is List or origin is abc.Sequence or origin is abc.MutableSequence:
        item_annotation = get_args(annotation)[0] if get_args(annotation) else Any
        return {
            "type": "array",
            "items": _annotation_to_schema(item_annotation),
        }

    if origin in {dict, Dict, abc.Mapping, abc.MutableMapping}:
        return {"type": "object"}

    if origin is Union:
        literals = [arg for arg in get_args(annotation) if arg is not type(None)]  # noqa: E721
        literal_schema = _try_literal_schema(literals)
        if literal_schema:
            return literal_schema
        return {"type": "string"}

    if origin is Literal:
        values = list(get_args(annotation))
        return _literal_schema(values)

    return {"type": "string"}


def _primitive_schema(annotation: Any) -> Dict[str, Any]:
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        values = [member.value for member in annotation]
        schema = _literal_schema(values)
        return schema if schema else {"type": "string"}

    if annotation in {str}:
        return {"type": "string"}
    if annotation in {int}:
        return {"type": "integer"}
    if annotation in {float}:
        return {"type": "number"}
    if annotation in {bool}:
        return {"type": "boolean"}
    if annotation in {dict, abc.Mapping}:
        return {"type": "object"}
    if annotation in {list, abc.Sequence}:
        return {"type": "array", "items": {"type": "string"}}

    return {"type": "string"}


def _apply_param_meta(schema: Dict[str, Any], meta: ParamMeta | None) -> Dict[str, Any]:
    if meta is None:
        return schema
    updated = dict(schema)
    if meta.description:
        updated["description"] = meta.description
    if meta.enum:
        updated["enum"] = list(meta.enum)
        inferred = _infer_literal_type(meta.enum)
        if inferred:
            updated["type"] = inferred
    return updated


def _literal_schema(values: Sequence[Any]) -> Dict[str, Any]:
    if not values:
        return {"type": "string"}
    schema: Dict[str, Any] = {"enum": list(values)}
    literal_type = _infer_literal_type(values)
    if literal_type:
        schema["type"] = literal_type
    return schema


def _try_literal_schema(values: Sequence[Any]) -> Dict[str, Any] | None:
    if not values:
        return None
    literal_type = _infer_literal_type(values)
    if literal_type is None:
        return None
    return {"type": literal_type, "enum": list(values)}


def _infer_literal_type(values: Sequence[Any]) -> str | None:
    if all(isinstance(value, bool) for value in values):
        return "boolean"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return "integer"
    if all(isinstance(value, float) for value in values):
        return "number"
    if all(isinstance(value, str) for value in values):
        return "string"
    return None


__all__ = [
    "FunctionCatalog",
    "FunctionMetadata",
    "ParamMeta",
    "get_function_catalog",
]
