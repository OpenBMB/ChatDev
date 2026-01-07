"""Placeholder resolution for design configs."""


import re
from typing import Any, Dict, Mapping, MutableMapping, Sequence

from entity.configs.base import ConfigError, extend_path


_PLACEHOLDER_PATTERN = re.compile(r"\$\{([A-Za-z0-9_]+)\}")
_PLACEHOLDER_ONLY_PATTERN = re.compile(r"^\s*\$\{([A-Za-z0-9_]+)\}\s*$")


class PlaceholderResolver:
    """Resolve ``${VAR}`` placeholders within nested structures."""

    def __init__(self, env_lookup: Mapping[str, Any], root_vars: Mapping[str, Any]):
        self._env_lookup = dict(env_lookup)
        self._raw_root = dict(root_vars or {})
        self._resolved_root: Dict[str, Any] = {}

    @property
    def resolved_root(self) -> Dict[str, Any]:
        # include untouched root vars so undeclared-but-needed entries remain available
        merged = dict(self._raw_root)
        merged.update(self._resolved_root)
        return merged

    def resolve(self, data: MutableMapping[str, Any], *, path: str = "root") -> MutableMapping[str, Any]:
        if not isinstance(data, MutableMapping):
            raise ConfigError("YAML root must be a mapping", path=path)
        self._resolve_value(data, path, stack=())
        return data

    def _resolve_value(self, value: Any, path: str, *, stack: Sequence[str]) -> Any:
        if isinstance(value, str):
            return self._resolve_string(value, path, stack)
        if isinstance(value, list):
            for idx, item in enumerate(value):
                value[idx] = self._resolve_value(item, extend_path(path, f"[{idx}]"), stack=stack)
            return value
        if isinstance(value, MutableMapping):
            for key in list(value.keys()):
                child_path = extend_path(path, str(key))
                value[key] = self._resolve_value(value[key], child_path, stack=stack)
            return value
        return value

    def _resolve_string(self, raw: str, path: str, stack: Sequence[str]) -> Any:
        only_match = _PLACEHOLDER_ONLY_PATTERN.fullmatch(raw)
        if only_match:
            var_name = only_match.group(1)
            return self._lookup(var_name, path, stack)

        def replacer(match: re.Match[str]) -> str:
            var_name = match.group(1)
            resolved = self._lookup(var_name, path, stack)
            return str(resolved)

        return _PLACEHOLDER_PATTERN.sub(replacer, raw)

    def _lookup(self, name: str, path: str, stack: Sequence[str]) -> Any:
        if name in self._resolved_root:
            return self._resolved_root[name]
        if name in stack:
            raise ConfigError(f"Detected placeholder cycle referencing '{name}'", path)
        if name in self._raw_root:
            resolved = self._resolve_value(self._raw_root[name], extend_path("vars", name), stack=stack + (name,))
            self._resolved_root[name] = resolved
            return resolved
        if name in self._env_lookup:
            return self._env_lookup[name]
        raise ConfigError(f"Unresolved placeholder '${{{name}}}'", path)


def resolve_design_placeholders(data: MutableMapping[str, Any], *, env_lookup: Mapping[str, Any], path: str = "root") -> Dict[str, Any]:
    """Resolve placeholders in-place and return the resolved root vars."""
    resolver = PlaceholderResolver(env_lookup, data.get("vars") or {})
    resolver.resolve(data, path=path)
    data["vars"] = resolver.resolved_root
    return resolver.resolved_root


def resolve_mapping_with_vars(
    data: MutableMapping[str, Any],
    *,
    env_lookup: Mapping[str, Any],
    vars_map: Mapping[str, Any],
    path: str = "root",
) -> MutableMapping[str, Any]:
    """Resolve placeholders using an explicit vars map without mutating it."""
    resolver = PlaceholderResolver(env_lookup, vars_map)
    return resolver.resolve(data, path=path)
