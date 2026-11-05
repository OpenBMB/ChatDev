"""Exact host/runtime path translation for formal sandbox execution.

The formal executor has two namespaces: private host paths used to construct
mounts and ``/app`` paths visible to tools and models.  Translation must be
based on the declared sandbox scope, never on filename suffixes or task text.
"""

from __future__ import annotations

import os
import posixpath
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


PATH_NAMESPACE_PROTOCOL = "exact-runtime-path-map-v2"


class PathNamespaceError(ValueError):
    """A path cannot be represented inside the declared sandbox scope."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _host_identity(value: str | os.PathLike[str]) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(os.fspath(value))))


def _host_contains(root: str, candidate: str) -> bool:
    try:
        return os.path.commonpath([root, candidate]) == root
    except ValueError:
        return False


def _is_reparse_point(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction):
        try:
            if is_junction():
                return True
        except OSError:
            return True
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _reject_existing_indirection(root: str, candidate: str) -> None:
    """Reject every existing link-like component below an authorized route."""

    root_path = Path(root)
    candidate_path = Path(candidate)
    try:
        relative = candidate_path.relative_to(root_path)
    except ValueError as exc:
        raise PathNamespaceError(
            "host_path_escape",
            "Host path escapes its authorized sandbox route.",
        ) from exc
    current = root_path
    for part in (Path(), *relative.parts):
        if part != Path():
            current = current / part
        if not os.path.lexists(current):
            continue
        if current.is_symlink() or os.path.islink(current) or _is_reparse_point(current):
            raise PathNamespaceError(
                "host_path_indirection_forbidden",
                "Host path contains a symlink, junction, or reparse point.",
            )


def _runtime_identity(value: str) -> str:
    text = str(value or "")
    if "\\" in text:
        raise PathNamespaceError(
            "runtime_path_not_posix",
            f"Runtime paths must use Linux/POSIX separators: {value}",
        )
    if not text.startswith("/app"):
        raise PathNamespaceError(
            "runtime_path_outside_app",
            f"Runtime path must be rooted at /app: {value}",
        )
    normalized = posixpath.normpath(text)
    if normalized != "/app" and not normalized.startswith("/app/"):
        raise PathNamespaceError(
            "runtime_path_escape",
            f"Runtime path escapes /app: {value}",
        )
    return normalized


def _runtime_contains(root: str, candidate: str) -> bool:
    root_path = PurePosixPath(root)
    candidate_path = PurePosixPath(candidate)
    return candidate_path == root_path or root_path in candidate_path.parents


@dataclass(frozen=True)
class _Route:
    host_path: str
    runtime_path: str
    path_kind: str
    purpose: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], *, purpose: str) -> "_Route":
        host = str(value.get("host_path") or "")
        runtime = str(value.get("runtime_path") or "")
        if not host or not runtime:
            raise PathNamespaceError(
                "path_route_incomplete",
                f"{purpose} route requires host_path and runtime_path",
            )
        if not os.path.isabs(host):
            raise PathNamespaceError(
                "host_path_not_absolute",
                f"{purpose} host path must be absolute",
            )
        path_kind = str(value.get("path_kind") or "directory")
        if path_kind not in {"file", "directory"}:
            raise PathNamespaceError(
                "path_kind_invalid",
                f"{purpose} route has an invalid path kind",
            )
        return cls(
            host_path=_host_identity(host),
            runtime_path=_runtime_identity(runtime),
            path_kind=path_kind,
            purpose=purpose,
        )


class RuntimePathMap:
    """Immutable, scope-derived translator for one formal Case execution."""

    protocol = PATH_NAMESPACE_PROTOCOL

    def __init__(
        self,
        *,
        public_inputs: Sequence[_Route],
        writable_root: _Route,
        runtime_roots: Sequence[_Route],
        masked_roots: Sequence[_Route],
        hidden_roots: Sequence[_Route],
    ) -> None:
        self.public_inputs = tuple(public_inputs)
        self.writable_root = writable_root
        self.runtime_roots = tuple(runtime_roots)
        self.masked_roots = tuple(masked_roots)
        self.hidden_roots = tuple(hidden_roots)
        self._validate_route_contract()

    @staticmethod
    def _routes_overlap(first: _Route, second: _Route) -> bool:
        host_overlap = (
            _host_contains(first.host_path, second.host_path)
            if first.path_kind == "directory"
            else first.host_path == second.host_path
        ) or (
            _host_contains(second.host_path, first.host_path)
            if second.path_kind == "directory"
            else second.host_path == first.host_path
        )
        runtime_overlap = (
            _runtime_contains(first.runtime_path, second.runtime_path)
            if first.path_kind == "directory"
            else first.runtime_path == second.runtime_path
        ) or (
            _runtime_contains(second.runtime_path, first.runtime_path)
            if second.path_kind == "directory"
            else second.runtime_path == first.runtime_path
        )
        return host_overlap or runtime_overlap

    @staticmethod
    def _route_obscures(first: _Route, second: _Route) -> bool:
        """Return whether ``first`` would make ``second`` unreachable.

        A broader writable/runtime route may temporarily contain an exact
        public snapshot while a formal step scope is being derived.  The
        public route is resolved first and the final executor scope replaces
        that broad writable route with an isolated attempt directory.  The
        inverse is ambiguous: a public directory must never contain a
        writable, runtime, or protected route.
        """

        return (
            first.host_path == second.host_path
            or first.runtime_path == second.runtime_path
            or (
                first.path_kind == "directory"
                and _host_contains(first.host_path, second.host_path)
            )
            or (
                first.path_kind == "directory"
                and _runtime_contains(first.runtime_path, second.runtime_path)
            )
        )

    def _validate_route_contract(self) -> None:
        """Reject ambiguous aliases before any payload crosses the boundary."""

        for index, route in enumerate(self.public_inputs):
            for other in self.public_inputs[index + 1 :]:
                if self._routes_overlap(route, other):
                    raise PathNamespaceError(
                        "public_input_route_collision",
                        "Public input routes must be one-to-one and non-overlapping.",
                    )
            if self._route_obscures(route, self.writable_root):
                raise PathNamespaceError(
                    "public_input_writable_route_collision",
                    "A public input route cannot obscure the writable route.",
                )
            for runtime_root in self.runtime_roots:
                if self._route_obscures(route, runtime_root):
                    raise PathNamespaceError(
                        "public_input_runtime_route_collision",
                        "A public input route cannot obscure a runtime route.",
                    )
            for protected in self.hidden_roots:
                if self._routes_overlap(route, protected):
                    raise PathNamespaceError(
                        "public_input_hidden_route_collision",
                        "A public input route cannot overlap a hidden route.",
                    )
            for protected in self.masked_roots:
                if self._route_obscures(route, protected):
                    raise PathNamespaceError(
                        "public_input_masked_route_collision",
                        "A public input route cannot obscure a masked route.",
                    )

    @classmethod
    def from_scope(cls, scope: Mapping[str, Any]) -> "RuntimePathMap":
        if not isinstance(scope, Mapping) or not scope:
            raise PathNamespaceError(
                "sandbox_scope_missing",
                "Formal path translation requires an explicit sandbox scope.",
            )

        def routes(name: str, purpose: str) -> tuple[_Route, ...]:
            raw = scope.get(name)
            if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
                raise PathNamespaceError(
                    "sandbox_scope_invalid",
                    f"sandbox scope {name} must be a sequence",
                )
            if any(not isinstance(item, Mapping) for item in raw):
                raise PathNamespaceError(
                    "sandbox_scope_invalid",
                    f"sandbox scope {name} contains a non-mapping route",
                )
            normalized = tuple(
                _Route.from_mapping(item, purpose=purpose) for item in raw
            )
            if name == "runtime_roots" and not normalized:
                raise PathNamespaceError(
                    "sandbox_scope_invalid",
                    f"sandbox scope {name} cannot be empty",
                )
            return normalized

        writable = scope.get("writable_root")
        if not isinstance(writable, Mapping):
            raise PathNamespaceError(
                "sandbox_scope_invalid",
                "sandbox scope writable_root must be a mapping",
            )
        return cls(
            public_inputs=routes("public_inputs", "public_input"),
            writable_root=_Route.from_mapping(writable, purpose="writable_root"),
            runtime_roots=routes("runtime_roots", "runtime_root"),
            masked_roots=routes("masked_roots", "masked"),
            hidden_roots=routes("hidden_roots", "hidden"),
        )

    @staticmethod
    def _is_host_absolute(value: str) -> bool:
        return os.path.isabs(value)

    def _public_host_route(self, candidate: str) -> _Route | None:
        for route in self.public_inputs:
            if candidate == route.host_path:
                return route
            if route.path_kind == "directory" and _host_contains(route.host_path, candidate):
                return route
        return None

    def _public_runtime_route(self, candidate: str) -> _Route | None:
        for route in self.public_inputs:
            if candidate == route.runtime_path:
                return route
            if route.path_kind == "directory" and _runtime_contains(route.runtime_path, candidate):
                return route
        return None

    @staticmethod
    def _relative_host_path(route: _Route, candidate: str) -> str:
        relative = os.path.relpath(candidate, route.host_path)
        if relative == ".":
            return route.runtime_path
        return str(PurePosixPath(route.runtime_path, *Path(relative).parts))

    @staticmethod
    def _relative_runtime_path(route: _Route, candidate: str) -> str:
        runtime_root = PurePosixPath(route.runtime_path)
        runtime_candidate = PurePosixPath(candidate)
        relative = runtime_candidate.relative_to(runtime_root)
        if not relative.parts:
            host = route.host_path
        else:
            host = os.path.join(route.host_path, *relative.parts)
        normalized = _host_identity(host)
        _reject_existing_indirection(route.host_path, normalized)
        return normalized

    def host_to_runtime(self, value: str | os.PathLike[str]) -> str:
        candidate = _host_identity(value)
        public = self._public_host_route(candidate)
        if public is not None:
            _reject_existing_indirection(public.host_path, candidate)
            return self._relative_host_path(public, candidate)

        for route in (self.writable_root, *self.runtime_roots):
            if _host_contains(route.host_path, candidate):
                # Runtime roots are mounted before masks.  Never translate a
                # hidden/masked descendant unless an exact public/writable
                # route above has already authorized it.
                if any(_host_contains(item.host_path, candidate) for item in self.hidden_roots):
                    break
                if route.purpose == "runtime_root" and any(
                    _host_contains(item.host_path, candidate) for item in self.masked_roots
                ):
                    break
                _reject_existing_indirection(route.host_path, candidate)
                return self._relative_host_path(route, candidate)
        raise PathNamespaceError(
            "host_path_not_in_sandbox_scope",
            "Host path is not represented by the current sandbox scope.",
        )

    def runtime_to_host(self, value: str) -> str:
        """Resolve one authorized ``/app`` path into its private host route."""

        candidate = _runtime_identity(value)
        public = self._public_runtime_route(candidate)
        if public is not None:
            return self._relative_runtime_path(public, candidate)
        if _runtime_contains(self.writable_root.runtime_path, candidate):
            return self._relative_runtime_path(self.writable_root, candidate)
        if any(_runtime_contains(item.runtime_path, candidate) for item in self.hidden_roots):
            raise PathNamespaceError(
                "runtime_path_hidden",
                "Runtime path targets a hidden sandbox root.",
            )
        if any(_runtime_contains(item.runtime_path, candidate) for item in self.masked_roots):
            raise PathNamespaceError(
                "runtime_path_masked",
                "Runtime path targets a masked sandbox root.",
            )
        for route in self.runtime_roots:
            if _runtime_contains(route.runtime_path, candidate):
                return self._relative_runtime_path(route, candidate)
        raise PathNamespaceError(
            "runtime_path_not_in_sandbox_scope",
            "Runtime path is not represented by the current sandbox scope.",
        )

    def validate_runtime(self, value: str) -> str:
        candidate = _runtime_identity(value)
        if self._public_runtime_route(candidate) is not None:
            return candidate
        if _runtime_contains(self.writable_root.runtime_path, candidate):
            return candidate
        if any(_runtime_contains(item.runtime_path, candidate) for item in self.hidden_roots):
            raise PathNamespaceError(
                "runtime_path_hidden",
                "Runtime path targets a hidden sandbox root.",
            )
        if any(_runtime_contains(item.runtime_path, candidate) for item in self.masked_roots):
            raise PathNamespaceError(
                "runtime_path_masked",
                "Runtime path targets a masked sandbox root.",
            )
        if any(_runtime_contains(item.runtime_path, candidate) for item in self.runtime_roots):
            return candidate
        raise PathNamespaceError(
            "runtime_path_not_in_sandbox_scope",
            "Runtime path is not represented by the current sandbox scope.",
        )

    def to_runtime_scalar(self, value: str) -> str:
        text = str(value)
        if "\\" not in text and (
            text == "/app" or text.startswith("/app/")
        ):
            return self.validate_runtime(text)
        if self._is_host_absolute(text):
            return self.host_to_runtime(text)
        return text

    def to_runtime_tree(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): self.to_runtime_tree(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self.to_runtime_tree(item) for item in value]
        if isinstance(value, str):
            return self.to_runtime_scalar(value)
        return value

    def map_path_tree(self, value: Any) -> Any:
        """Map a path-typed structured value without reparsing opaque strings."""

        return self.to_runtime_tree(value)

    def runtime_import_roots(
        self,
        extra_dirs: Sequence[str | os.PathLike[str]] = (),
    ) -> list[str]:
        """Return deterministic Python roots already exposed by this scope.

        The method grants no filesystem access: every entry must map through an
        existing runtime/writable/public-directory route.  In particular the
        workspace parent can never be smuggled back into formal ``PYTHONPATH``.
        """

        candidates: list[str] = [
            *(route.host_path for route in self.runtime_roots),
            self.writable_root.host_path,
            *(os.fspath(item) for item in extra_dirs),
        ]
        roots: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            text = os.fspath(candidate)
            if "\\" not in text and (
                text == "/app" or text.startswith("/app/")
            ):
                runtime = self.validate_runtime(text)
                host = self.runtime_to_host(runtime)
            else:
                host = _host_identity(text)
                runtime = self.host_to_runtime(host)
            if os.path.exists(host) and not os.path.isdir(host):
                raise PathNamespaceError(
                    "runtime_import_root_not_directory",
                    "A formal Python import root is not a directory.",
                )
            if runtime in seen:
                continue
            seen.add(runtime)
            roots.append(runtime)
        return roots
