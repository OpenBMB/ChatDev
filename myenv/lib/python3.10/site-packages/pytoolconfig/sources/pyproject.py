"""Source for pyproject.toml files or more generally toml files."""
from __future__ import annotations

import sys
from pathlib import Path

from pytoolconfig.sources.source import Source
from pytoolconfig.types import Key
from pytoolconfig.universal_config import UniversalConfig
from pytoolconfig.utils import (
    _dict_to_dataclass,
    find_config_file,
    max_py_version,
    min_py_version,
    parse_dependencies,
)

if sys.version_info < (3, 11, 0):
    import tomli as tomllib
else:
    import tomllib


class PyProject(Source):
    """Source for pyproject.toml and pytool.toml files.

    Can be extended to other toml files.
    """

    tool: str
    toml_dict: dict | None = None
    name: str = "pyproject.toml"
    description: str = """
    PEP 518 defines pyproject.toml as a configuration file to store build system
    requirements for Python projects. With the help of tools like Poetry or Flit
    it can fully replace the need for setup.py and setup.cfg files.
    """  # taken from black.
    file: Path | None

    def __init__(
        self,
        working_directory: Path,
        tool: str,
        bases: list[str] | None = None,
        recursive: bool = True,
    ):
        """Initialize the TOML configuration.

        :param working_directory: Working Directory
        :param tool: name of your tool. Will read configuration from [tool.yourtool]
        :param bases: Base files/folders to look for (besides pyproject.toml)
        :param recursive: search recursively up the directory tree for the file.
        """
        if recursive:
            self.file = find_config_file(working_directory, "pyproject.toml", bases)
        else:
            self.file = working_directory / "pyproject.toml"
        self.tool = tool

    def _read(self) -> bool:
        if not self.file or not self.file.exists():
            return False
        self.toml_dict = tomllib.loads(self.file.read_text())
        if self.toml_dict is None:
            return False
        if "tool" not in self.toml_dict.keys():
            return False
        return self.tool in self.toml_dict["tool"].keys()

    def parse(self) -> dict[str, Key] | None:
        """Parse the TOML file."""
        if not self._read():
            return None
        assert self.toml_dict
        return self.toml_dict["tool"][self.tool]

    def universalconfig(self) -> UniversalConfig:
        """Parse the file for the universal config object's fields.

        Only implement the relevant fields such as minimum python version.

        Pre: file was read but tool isn't necessarily in file.
        """
        if not self.toml_dict:
            return UniversalConfig()
        config: UniversalConfig
        if "pytoolconfig" in self.toml_dict.get("tool", {}).keys():
            config = _dict_to_dataclass(
                UniversalConfig, self.toml_dict["tool"]["pytoolconfig"]
            )
        else:
            config = UniversalConfig()
        if "project" in self.toml_dict.keys():
            project = self.toml_dict["project"]
            if "requires-python" in project.keys():
                raw_python_ver = project["requires-python"]
                config.min_py_version = min_py_version(raw_python_ver)
                config.max_py_version = max_py_version(raw_python_ver)
            if "dependencies" in project:
                dependencies = parse_dependencies(project["dependencies"])
                config.dependencies = list(dependencies)
            if "optional-dependencies" in project:
                optional_deps = {}
                for group, deps in project["optional-dependencies"].items():
                    optional_deps[group] = list(parse_dependencies(deps))
                config.optional_dependencies = optional_deps
            if "version" in project:
                config.version = project["version"]
        return config
