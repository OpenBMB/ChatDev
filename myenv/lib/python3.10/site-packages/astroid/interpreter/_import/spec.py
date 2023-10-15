# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import abc
import enum
import importlib
import importlib.machinery
import importlib.util
import os
import pathlib
import sys
import types
import zipimport
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, NamedTuple

from astroid.const import PY310_PLUS
from astroid.modutils import EXT_LIB_DIRS

from . import util

if sys.version_info >= (3, 8):
    from typing import Literal, Protocol
else:
    from typing_extensions import Literal, Protocol


# The MetaPathFinder protocol comes from typeshed, which says:
# Intentionally omits one deprecated and one optional method of `importlib.abc.MetaPathFinder`
class _MetaPathFinder(Protocol):
    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: types.ModuleType | None = ...,
    ) -> importlib.machinery.ModuleSpec | None:
        ...  # pragma: no cover


class ModuleType(enum.Enum):
    """Python module types used for ModuleSpec."""

    C_BUILTIN = enum.auto()
    C_EXTENSION = enum.auto()
    PKG_DIRECTORY = enum.auto()
    PY_CODERESOURCE = enum.auto()
    PY_COMPILED = enum.auto()
    PY_FROZEN = enum.auto()
    PY_RESOURCE = enum.auto()
    PY_SOURCE = enum.auto()
    PY_ZIPMODULE = enum.auto()
    PY_NAMESPACE = enum.auto()


_MetaPathFinderModuleTypes: dict[str, ModuleType] = {
    # Finders created by setuptools editable installs
    "_EditableFinder": ModuleType.PY_SOURCE,
    "_EditableNamespaceFinder": ModuleType.PY_NAMESPACE,
    # Finders create by six
    "_SixMetaPathImporter": ModuleType.PY_SOURCE,
}

_EditableFinderClasses: set[str] = {
    "_EditableFinder",
    "_EditableNamespaceFinder",
}


class ModuleSpec(NamedTuple):
    """Defines a class similar to PEP 420's ModuleSpec.

    A module spec defines a name of a module, its type, location
    and where submodules can be found, if the module is a package.
    """

    name: str
    type: ModuleType | None
    location: str | None = None
    origin: str | None = None
    submodule_search_locations: Sequence[str] | None = None


class Finder:
    """A finder is a class which knows how to find a particular module."""

    def __init__(self, path: Sequence[str] | None = None) -> None:
        self._path = path or sys.path

    @abc.abstractmethod
    def find_module(
        self,
        modname: str,
        module_parts: Sequence[str],
        processed: list[str],
        submodule_path: Sequence[str] | None,
    ) -> ModuleSpec | None:
        """Find the given module.

        Each finder is responsible for each protocol of finding, as long as
        they all return a ModuleSpec.

        :param modname: The module which needs to be searched.
        :param module_parts: It should be a list of strings,
                                  where each part contributes to the module's
                                  namespace.
        :param processed: What parts from the module parts were processed
                               so far.
        :param submodule_path: A list of paths where the module
                                    can be looked into.
        :returns: A ModuleSpec, describing how and where the module was found,
                  None, otherwise.
        """

    def contribute_to_path(
        self, spec: ModuleSpec, processed: list[str]
    ) -> Sequence[str] | None:
        """Get a list of extra paths where this finder can search."""


class ImportlibFinder(Finder):
    """A finder based on the importlib module."""

    _SUFFIXES: Sequence[tuple[str, ModuleType]] = (
        [(s, ModuleType.C_EXTENSION) for s in importlib.machinery.EXTENSION_SUFFIXES]
        + [(s, ModuleType.PY_SOURCE) for s in importlib.machinery.SOURCE_SUFFIXES]
        + [(s, ModuleType.PY_COMPILED) for s in importlib.machinery.BYTECODE_SUFFIXES]
    )

    def find_module(
        self,
        modname: str,
        module_parts: Sequence[str],
        processed: list[str],
        submodule_path: Sequence[str] | None,
    ) -> ModuleSpec | None:
        if submodule_path is not None:
            submodule_path = list(submodule_path)
        elif modname in sys.builtin_module_names:
            return ModuleSpec(
                name=modname,
                location=None,
                type=ModuleType.C_BUILTIN,
            )
        else:
            try:
                spec = importlib.util.find_spec(modname)
                if (
                    spec
                    and spec.loader  # type: ignore[comparison-overlap] # noqa: E501
                    is importlib.machinery.FrozenImporter
                ):
                    # No need for BuiltinImporter; builtins handled above
                    return ModuleSpec(
                        name=modname,
                        location=getattr(spec.loader_state, "filename", None),
                        type=ModuleType.PY_FROZEN,
                    )
            except ValueError:
                pass
            submodule_path = sys.path

        for entry in submodule_path:
            package_directory = os.path.join(entry, modname)
            for suffix in (".py", importlib.machinery.BYTECODE_SUFFIXES[0]):
                package_file_name = "__init__" + suffix
                file_path = os.path.join(package_directory, package_file_name)
                if os.path.isfile(file_path):
                    return ModuleSpec(
                        name=modname,
                        location=package_directory,
                        type=ModuleType.PKG_DIRECTORY,
                    )
            for suffix, type_ in ImportlibFinder._SUFFIXES:
                file_name = modname + suffix
                file_path = os.path.join(entry, file_name)
                if os.path.isfile(file_path):
                    return ModuleSpec(name=modname, location=file_path, type=type_)
        return None

    def contribute_to_path(
        self, spec: ModuleSpec, processed: list[str]
    ) -> Sequence[str] | None:
        if spec.location is None:
            # Builtin.
            return None

        if _is_setuptools_namespace(Path(spec.location)):
            # extend_path is called, search sys.path for module/packages
            # of this name see pkgutil.extend_path documentation
            path = [
                os.path.join(p, *processed)
                for p in sys.path
                if os.path.isdir(os.path.join(p, *processed))
            ]
        elif spec.name == "distutils" and not any(
            spec.location.lower().startswith(ext_lib_dir.lower())
            for ext_lib_dir in EXT_LIB_DIRS
        ):
            # virtualenv below 20.0 patches distutils in an unexpected way
            # so we just find the location of distutils that will be
            # imported to avoid spurious import-error messages
            # https://github.com/PyCQA/pylint/issues/5645
            # A regression test to create this scenario exists in release-tests.yml
            # and can be triggered manually from GitHub Actions
            distutils_spec = importlib.util.find_spec("distutils")
            if distutils_spec and distutils_spec.origin:
                origin_path = Path(
                    distutils_spec.origin
                )  # e.g. .../distutils/__init__.py
                path = [str(origin_path.parent)]  # e.g. .../distutils
            else:
                path = [spec.location]
        else:
            path = [spec.location]
        return path


class ExplicitNamespacePackageFinder(ImportlibFinder):
    """A finder for the explicit namespace packages."""

    def find_module(
        self,
        modname: str,
        module_parts: Sequence[str],
        processed: list[str],
        submodule_path: Sequence[str] | None,
    ) -> ModuleSpec | None:
        if processed:
            modname = ".".join(processed + [modname])
        if util.is_namespace(modname) and modname in sys.modules:
            submodule_path = sys.modules[modname].__path__
            return ModuleSpec(
                name=modname,
                location="",
                origin="namespace",
                type=ModuleType.PY_NAMESPACE,
                submodule_search_locations=submodule_path,
            )
        return None

    def contribute_to_path(
        self, spec: ModuleSpec, processed: list[str]
    ) -> Sequence[str] | None:
        return spec.submodule_search_locations


class ZipFinder(Finder):
    """Finder that knows how to find a module inside zip files."""

    def __init__(self, path: Sequence[str]) -> None:
        super().__init__(path)
        for entry_path in path:
            if entry_path not in sys.path_importer_cache:
                try:
                    sys.path_importer_cache[entry_path] = zipimport.zipimporter(  # type: ignore[assignment]
                        entry_path
                    )
                except zipimport.ZipImportError:
                    continue

    def find_module(
        self,
        modname: str,
        module_parts: Sequence[str],
        processed: list[str],
        submodule_path: Sequence[str] | None,
    ) -> ModuleSpec | None:
        try:
            file_type, filename, path = _search_zip(module_parts)
        except ImportError:
            return None

        return ModuleSpec(
            name=modname,
            location=filename,
            origin="egg",
            type=file_type,
            submodule_search_locations=path,
        )


class PathSpecFinder(Finder):
    """Finder based on importlib.machinery.PathFinder."""

    def find_module(
        self,
        modname: str,
        module_parts: Sequence[str],
        processed: list[str],
        submodule_path: Sequence[str] | None,
    ) -> ModuleSpec | None:
        spec = importlib.machinery.PathFinder.find_spec(modname, path=submodule_path)
        if spec is not None:
            is_namespace_pkg = spec.origin is None
            location = spec.origin if not is_namespace_pkg else None
            module_type = ModuleType.PY_NAMESPACE if is_namespace_pkg else None
            return ModuleSpec(
                name=spec.name,
                location=location,
                origin=spec.origin,
                type=module_type,
                submodule_search_locations=list(spec.submodule_search_locations or []),
            )
        return spec

    def contribute_to_path(
        self, spec: ModuleSpec, processed: list[str]
    ) -> Sequence[str] | None:
        if spec.type == ModuleType.PY_NAMESPACE:
            return spec.submodule_search_locations
        return None


_SPEC_FINDERS = (
    ImportlibFinder,
    ZipFinder,
    PathSpecFinder,
    ExplicitNamespacePackageFinder,
)


def _is_setuptools_namespace(location: pathlib.Path) -> bool:
    try:
        with open(location / "__init__.py", "rb") as stream:
            data = stream.read(4096)
    except OSError:
        return False
    extend_path = b"pkgutil" in data and b"extend_path" in data
    declare_namespace = (
        b"pkg_resources" in data and b"declare_namespace(__name__)" in data
    )
    return extend_path or declare_namespace


def _get_zipimporters() -> Iterator[tuple[str, zipimport.zipimporter]]:
    for filepath, importer in sys.path_importer_cache.items():
        if isinstance(importer, zipimport.zipimporter):
            yield filepath, importer


def _search_zip(
    modpath: Sequence[str],
) -> tuple[Literal[ModuleType.PY_ZIPMODULE], str, str]:
    for filepath, importer in _get_zipimporters():
        if PY310_PLUS:
            found: Any = importer.find_spec(modpath[0])
        else:
            found = importer.find_module(modpath[0])
        if found:
            if PY310_PLUS:
                if not importer.find_spec(os.path.sep.join(modpath)):
                    raise ImportError(
                        "No module named %s in %s/%s"
                        % (".".join(modpath[1:]), filepath, modpath)
                    )
            elif not importer.find_module(os.path.sep.join(modpath)):
                raise ImportError(
                    "No module named %s in %s/%s"
                    % (".".join(modpath[1:]), filepath, modpath)
                )
            return (
                ModuleType.PY_ZIPMODULE,
                os.path.abspath(filepath) + os.path.sep + os.path.sep.join(modpath),
                filepath,
            )
    raise ImportError(f"No module named {'.'.join(modpath)}")


def _find_spec_with_path(
    search_path: Sequence[str],
    modname: str,
    module_parts: list[str],
    processed: list[str],
    submodule_path: Sequence[str] | None,
) -> tuple[Finder | _MetaPathFinder, ModuleSpec]:
    for finder in _SPEC_FINDERS:
        finder_instance = finder(search_path)
        spec = finder_instance.find_module(
            modname, module_parts, processed, submodule_path
        )
        if spec is None:
            continue
        return finder_instance, spec

    # Support for custom finders
    for meta_finder in sys.meta_path:
        # See if we support the customer import hook of the meta_finder
        meta_finder_name = meta_finder.__class__.__name__
        if meta_finder_name not in _MetaPathFinderModuleTypes:
            # Setuptools>62 creates its EditableFinders dynamically and have
            # "type" as their __class__.__name__. We check __name__ as well
            # to see if we can support the finder.
            try:
                meta_finder_name = meta_finder.__name__
            except AttributeError:
                continue
            if meta_finder_name not in _MetaPathFinderModuleTypes:
                continue

        module_type = _MetaPathFinderModuleTypes[meta_finder_name]

        # Meta path finders are supposed to have a find_spec method since
        # Python 3.4. However, some third-party finders do not implement it.
        # PEP302 does not refer to find_spec as well.
        # See: https://github.com/PyCQA/astroid/pull/1752/
        if not hasattr(meta_finder, "find_spec"):
            continue

        spec = meta_finder.find_spec(modname, submodule_path)
        if spec:
            return (
                meta_finder,
                ModuleSpec(
                    spec.name,
                    module_type,
                    spec.origin,
                    spec.origin,
                    spec.submodule_search_locations,
                ),
            )

    raise ImportError(f"No module named {'.'.join(module_parts)}")


def find_spec(modpath: list[str], path: Sequence[str] | None = None) -> ModuleSpec:
    """Find a spec for the given module.

    :type modpath: list or tuple
    :param modpath:
      split module's name (i.e name of a module or package split
      on '.'), with leading empty strings for explicit relative import

    :type path: list or None
    :param path:
      optional list of path where the module or package should be
      searched (use sys.path if nothing or None is given)

    :rtype: ModuleSpec
    :return: A module spec, which describes how the module was
             found and where.
    """
    _path = path or sys.path

    # Need a copy for not mutating the argument.
    modpath = modpath[:]

    submodule_path = None
    module_parts = modpath[:]
    processed: list[str] = []

    while modpath:
        modname = modpath.pop(0)
        finder, spec = _find_spec_with_path(
            _path, modname, module_parts, processed, submodule_path or path
        )
        processed.append(modname)
        if modpath:
            if isinstance(finder, Finder):
                submodule_path = finder.contribute_to_path(spec, processed)
            # If modname is a package from an editable install, update submodule_path
            # so that the next module in the path will be found inside of it using importlib.
            elif finder.__name__ in _EditableFinderClasses:
                submodule_path = spec.submodule_search_locations

        if spec.type == ModuleType.PKG_DIRECTORY:
            spec = spec._replace(submodule_search_locations=submodule_path)

    return spec
