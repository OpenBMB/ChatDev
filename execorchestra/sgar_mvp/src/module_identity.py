"""Canonical Python module identity checks for the formal SGAR process.

The repository historically made ``sgar_mvp/src`` importable as a top-level
``src`` package.  Importing the same file through both names creates distinct
class and exception identities.  This module detects that condition without
depending on task content and without serializing host paths.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping

from .pipeline_control import canonical_sha256


MODULE_IDENTITY_PROTOCOL = "sgar-canonical-module-identity-v1"
CANONICAL_SOURCE_PACKAGE = "sgar_mvp.src"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ModuleIdentityError(RuntimeError):
    """Structured startup failure raised before any paid work."""

    def __init__(self, failure_code: str) -> None:
        super().__init__(failure_code)
        self.failure_code = str(failure_code)
        self.failure_responsibility = "framework"
        self.failure_stage = "module_identity"
        self.retryable = False
        self.response_received = False


def _source_path(module: ModuleType) -> Path | None:
    origin = getattr(getattr(module, "__spec__", None), "origin", None)
    raw = origin or getattr(module, "__file__", None)
    if not raw or str(raw) in {"built-in", "frozen"}:
        return None
    path = Path(str(raw))
    if path.suffix.lower() in {".pyc", ".pyo"}:
        try:
            path = Path(importlib.util.source_from_cache(str(path)))
        except (ValueError, OSError):
            return None
    try:
        return path.resolve()
    except OSError:
        return None


def _relative_locator(path: Path, root: Path) -> str | None:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return None


def _canonical_name(locator: str) -> str:
    relative = Path(locator).relative_to("sgar_mvp/src")
    parts = list(relative.parts)
    filename = parts.pop()
    if filename == "__init__.py":
        suffix = parts
    else:
        suffix = [*parts, Path(filename).stem]
    return ".".join([CANONICAL_SOURCE_PACKAGE, *suffix])


def _production_python_files(root: Path) -> Iterable[Path]:
    package = root / "sgar_mvp"
    source_groups = (
        package.glob("*.py"),
        (package / "src").glob("*.py"),
        (package / "scripts").glob("*.py"),
    )
    paths = {path for group in source_groups for path in group if path.is_file()}
    yield from sorted(paths)


def _forbidden_src_imports(root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in _production_python_files(root):
        locator = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=locator)
        except (OSError, UnicodeError, SyntaxError) as exc:
            findings.append(
                {
                    "locator": locator,
                    "line": int(getattr(exc, "lineno", 0) or 0),
                    "kind": "source_parse_failed",
                }
            )
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module_name = str(node.module or "")
                if node.level == 0 and (
                    module_name == "src" or module_name.startswith("src.")
                ):
                    findings.append(
                        {
                            "locator": locator,
                            "line": int(node.lineno),
                            "kind": "top_level_src_import",
                        }
                    )
            elif isinstance(node, ast.Import):
                if any(
                    alias.name == "src" or alias.name.startswith("src.")
                    for alias in node.names
                ):
                    findings.append(
                        {
                            "locator": locator,
                            "line": int(node.lineno),
                            "kind": "top_level_src_import",
                        }
                    )
    return sorted(
        findings,
        key=lambda item: (item["locator"], item["line"], item["kind"]),
    )


def audit_canonical_module_identity(
    *,
    project_root: str | Path = PROJECT_ROOT,
    modules: Mapping[str, ModuleType] | None = None,
    search_path: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return a host-free audit of loaded and statically imported SGAR modules."""

    root = Path(project_root).resolve()
    source_root = (root / "sgar_mvp" / "src").resolve()
    loaded_modules = modules if modules is not None else sys.modules
    by_locator: dict[str, list[tuple[str, ModuleType]]] = {}
    for name, module in tuple(loaded_modules.items()):
        if not isinstance(module, ModuleType):
            continue
        source = _source_path(module)
        if source is None:
            continue
        locator = _relative_locator(source, root)
        if locator is None or not locator.startswith("sgar_mvp/src/"):
            if locator != "sgar_mvp/src/__init__.py":
                continue
        by_locator.setdefault(locator, []).append((str(name), module))

    duplicate_source_modules: list[dict[str, Any]] = []
    noncanonical_loaded_modules: list[dict[str, Any]] = []
    for locator, entries in sorted(by_locator.items()):
        unique_names = sorted({name for name, _module in entries})
        expected = _canonical_name(locator)
        module_objects = {id(module) for _name, module in entries}
        executable_aliases = {"__main__", "__mp_main__"}
        executable_module = bool(
            set(unique_names).issubset(executable_aliases)
            and len(module_objects) == 1
            and all(
                getattr(getattr(module, "__spec__", None), "name", None) == expected
                for _name, module in entries
            )
        )
        if len(unique_names) > 1 and not executable_module:
            duplicate_source_modules.append(
                {"source_locator": locator, "loaded_names": unique_names}
            )
        if unique_names != [expected] and not executable_module:
            noncanonical_loaded_modules.append(
                {
                    "source_locator": locator,
                    "expected_name": expected,
                    "loaded_names": unique_names,
                }
            )

    forbidden_sys_path_entries: list[str] = []
    for entry in tuple(search_path if search_path is not None else sys.path):
        if not str(entry).strip():
            continue
        try:
            resolved = Path(str(entry)).resolve()
        except OSError:
            continue
        if os.path.normcase(str(resolved)) == os.path.normcase(str(source_root.parent)):
            forbidden_sys_path_entries.append("sgar_mvp")

    forbidden_imports = _forbidden_src_imports(root)
    projection = {
        "protocol": MODULE_IDENTITY_PROTOCOL,
        "valid": not (
            duplicate_source_modules
            or noncanonical_loaded_modules
            or forbidden_sys_path_entries
            or forbidden_imports
        ),
        "duplicate_source_modules": duplicate_source_modules,
        "noncanonical_loaded_modules": noncanonical_loaded_modules,
        "forbidden_sys_path_entries": sorted(set(forbidden_sys_path_entries)),
        "forbidden_source_imports": forbidden_imports,
    }
    return {**projection, "audit_sha256": canonical_sha256(projection)}


def require_canonical_module_identity(
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> dict[str, Any]:
    audit = audit_canonical_module_identity(project_root=project_root)
    if not audit["valid"]:
        raise ModuleIdentityError("module_namespace_duplicate")
    return audit


__all__ = [
    "CANONICAL_SOURCE_PACKAGE",
    "MODULE_IDENTITY_PROTOCOL",
    "ModuleIdentityError",
    "audit_canonical_module_identity",
    "require_canonical_module_identity",
]
