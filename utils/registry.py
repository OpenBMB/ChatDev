"""Generic registry utilities for pluggable backend components."""

from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, Callable, Dict, Iterable, Optional


class RegistryError(RuntimeError):
    """Raised when registering duplicated or invalid entries."""


@dataclass(slots=True)
class RegistryEntry:
    name: str
    loader: Callable[[], Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def load(self) -> Any:
        return self.loader()


class Registry:
    """Lightweight registry with lazy module loading support."""

    def __init__(self, namespace: str) -> None:
        self.namespace = namespace
        self._entries: Dict[str, RegistryEntry] = {}

    def register(
        self,
        name: str,
        *,
        loader: Callable[[], Any] | None = None,
        target: Any | None = None,
        metadata: Optional[Dict[str, Any]] = None,
        module_path: str | None = None,
        attr_name: str | None = None,
    ) -> None:
        if name in self._entries:
            raise RegistryError(f"Duplicate registration for '{name}' in {self.namespace}")

        if loader is None:
            if target is None and module_path is None:
                raise RegistryError("Must provide loader, target, or module_path/attr_name")
            if target is not None:
                loader = lambda target=target: target
            else:
                if not attr_name:
                    raise RegistryError("module_path requires attr_name")

                def _lazy_loader(mod_path: str = module_path, attr: str = attr_name) -> Any:
                    module = import_module(mod_path)
                    return getattr(module, attr)

                loader = _lazy_loader

        entry = RegistryEntry(name=name, loader=loader, metadata=dict(metadata or {}))
        self._entries[name] = entry

    def get(self, name: str) -> RegistryEntry:
        try:
            return self._entries[name]
        except KeyError as exc:
            raise RegistryError(f"Unknown entry '{name}' in {self.namespace}") from exc

    def names(self) -> Iterable[str]:
        return self._entries.keys()

    def items(self) -> Iterable[tuple[str, RegistryEntry]]:
        return self._entries.items()

    def metadata_for(self, name: str) -> Dict[str, Any]:
        return dict(self.get(name).metadata)

