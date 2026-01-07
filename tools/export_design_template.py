"""CLI for exporting DesignConfig YAML templates from typed schemas."""

import argparse
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

import yaml

from runtime.bootstrap.schema import ensure_schema_registry_populated
from entity.configs import BaseConfig, DesignConfig
from entity.configs.base import ChildKey, ConfigFieldSpec


TYPE_ALIASES: Dict[str, str] = {
    "str": "string",
    "string": "string",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "list": "list",
    "dict": "dict",
    "mapping": "mapping",
    "enum": "enum",
}


ensure_schema_registry_populated()


class DesignTemplateEmitter:
    """Builds human-oriented YAML templates from config schemas."""

    def __init__(self, root_cls: type[BaseConfig] = DesignConfig):
        self.root_cls = root_cls

    def build(self, *, version: str | None = None) -> OrderedDict[str, Any]:
        document = self._emit_config(self.root_cls, stack=[])
        if version:
            document["version"] = version
        return document

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _emit_config(self, config_cls: type[BaseConfig], *, stack: list[type[BaseConfig]]) -> OrderedDict[str, Any]:
        if config_cls in stack:
            return OrderedDict(
                {
                    self._format_recursive_placeholder(config_cls, stack):
                        "See earlier definition to avoid infinite recursion",
                }
            )

        stack.append(config_cls)
        payload: "OrderedDict[str, Any]" = OrderedDict()
        field_specs = config_cls.field_specs()
        try:
            for name, spec in field_specs.items():
                payload[name] = self._emit_field(config_cls, spec, stack=stack)
        finally:
            stack.pop()
        return payload

    def _emit_field(self, parent_cls: type[BaseConfig], spec: ConfigFieldSpec, *, stack: list[type[BaseConfig]]) -> Any:
        routes = self._routes_for_field(parent_cls, spec.name)
        if routes:
            variant_block: "OrderedDict[str, Any]" = OrderedDict()
            for label, child_cls in routes:
                variant_block[label] = self._wrap_with_container(
                    spec,
                    self._emit_config(child_cls, stack=stack),
                )
            return variant_block

        if spec.child is not None:
            return self._wrap_with_container(
                spec,
                self._emit_config(spec.child, stack=stack),
            )

        hint = (spec.type_hint or "value").lower()
        if self._looks_like_dict(hint):
            value_placeholder = self._format_placeholder(type_hint="value", required=True, default=None, enum=None)
            return OrderedDict({"<key>": value_placeholder})
        if self._looks_like_list(hint):
            inner_hint = self._extract_inner_type(spec.type_hint)
            entry_placeholder = self._format_placeholder(
                type_hint=inner_hint,
                required=spec.required,
                default=None,
                enum=spec.enum,
            )
            return [entry_placeholder]
        return self._format_placeholder_from_spec(spec)

    def _routes_for_field(self, parent_cls: type[BaseConfig], field_name: str) -> Sequence[Tuple[str, type[BaseConfig]]]:
        routes: list[Tuple[str, type[BaseConfig]]] = []
        for key, child in parent_cls.child_routes().items():
            if key.field != field_name:
                continue
            label = self._format_variant_label(key)
            routes.append((label, child))
        return routes

    def _wrap_with_container(self, spec: ConfigFieldSpec, payload: Any) -> Any:
        hint = (spec.type_hint or "").lower()
        if self._looks_like_list(hint):
            return [payload]
        return payload

    # ------------------------------------------------------------------
    # Formatting utilities
    # ------------------------------------------------------------------

    def _format_placeholder_from_spec(self, spec: ConfigFieldSpec) -> str:
        return self._format_placeholder(
            type_hint=spec.type_hint,
            required=spec.required,
            default=spec.default,
            enum=spec.enum,
        )

    def _format_placeholder(
        self,
        *,
        type_hint: str | None,
        required: bool,
        default: Any,
        enum: Sequence[Any] | None,
    ) -> str:
        type_label = self._normalize_type(type_hint)
        default_label = self._format_default(enum=enum, default=default, required=required)
        return f"<{type_label}> | {default_label}"

    def _format_default(
        self,
        *,
        enum: Sequence[Any] | None,
        default: Any,
        required: bool,
    ) -> str:
        if enum:
            return f"[{', '.join(map(str, enum))}]"
        if default is None:
            return "required" if required else "None"
        if isinstance(default, bool):
            return "true" if default else "false"
        if isinstance(default, (int, float)):
            return str(default)
        if isinstance(default, str):
            return f'"{default}"'
        if isinstance(default, Mapping):
            return "{}"
        if isinstance(default, Sequence) and not isinstance(default, (str, bytes)):
            return "[]"
        return str(default)

    def _normalize_type(self, type_hint: str | None) -> str:
        if not type_hint:
            return "value"
        normalized = type_hint.strip()
        base = normalized.split("[", 1)[0].split("|", 1)[0].strip().lower()
        alias = TYPE_ALIASES.get(base)
        if alias:
            normalized = normalized.replace(base, alias, 1)
        return normalized

    @staticmethod
    def _looks_like_list(type_hint: str) -> bool:
        return type_hint.startswith("list") or type_hint.endswith("[]")

    @staticmethod
    def _looks_like_dict(type_hint: str) -> bool:
        return type_hint.startswith("dict") or "mapping" in type_hint

    @staticmethod
    def _extract_inner_type(type_hint: str | None) -> str:
        if not type_hint or "[" not in type_hint or "]" not in type_hint:
            return "value"
        start = type_hint.find("[") + 1
        end = type_hint.rfind("]")
        inner = type_hint[start:end].strip()
        return inner or "value"

    @staticmethod
    def _format_variant_label(key: ChildKey) -> str:
        if key.value is None:
            return f"<variant[{key.field}]>"
        return f"<variant[{key.field}]={key.value}>"

    @staticmethod
    def _format_recursive_placeholder(config_cls: type[BaseConfig], stack: list[type[BaseConfig]]) -> str:
        cycle = " → ".join(cls.__name__ for cls in (*stack, config_cls))
        return f"<recursive[{config_cls.__name__}] path: {cycle}>"


def dump_yaml(data: Mapping[str, Any], path: Path) -> None:
    class _Dumper(yaml.SafeDumper):
        pass

    def _represent_ordered_dict(dumper: yaml.SafeDumper, value: OrderedDict) -> yaml.nodes.MappingNode:  # type: ignore
        return dumper.represent_dict(value.items())

    _Dumper.add_representer(OrderedDict, _represent_ordered_dict)
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle, Dumper=_Dumper, sort_keys=False, allow_unicode=True)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export design_0.4.0 YAML templates from config schemas")
    parser.add_argument("--output", type=Path, required=True, help="Primary output YAML path")
    parser.add_argument("--version", type=str, default=None, help="Version string to pin in the template")
    parser.add_argument(
        "--mirror",
        type=Path,
        nargs="*",
        default=(),
        help="Optional additional paths that should receive the same generated document",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    emitter = DesignTemplateEmitter(DesignConfig)
    document = emitter.build(version=args.version)
    targets = [args.output, *args.mirror]
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        dump_yaml(document, target)
    print("Exported design template to:")
    for target in targets:
        print(f" - {target.resolve()}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    # uv run -m tools.export_design_template --output yaml_template/design.yaml
    raise SystemExit(main())
