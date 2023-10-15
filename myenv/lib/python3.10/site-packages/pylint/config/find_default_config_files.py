# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import configparser
import os
import sys
import warnings
from collections.abc import Iterator
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

RC_NAMES = (Path("pylintrc"), Path(".pylintrc"))
CONFIG_NAMES = RC_NAMES + (Path("pyproject.toml"), Path("setup.cfg"))


def _toml_has_config(path: Path | str) -> bool:
    with open(path, mode="rb") as toml_handle:
        try:
            content = tomllib.load(toml_handle)
        except tomllib.TOMLDecodeError as error:
            print(f"Failed to load '{path}': {error}")
            return False
    return "pylint" in content.get("tool", [])


def _cfg_has_config(path: Path | str) -> bool:
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except configparser.Error:
        return False
    return any(section.startswith("pylint.") for section in parser.sections())


def _yield_default_files() -> Iterator[Path]:
    """Iterate over the default config file names and see if they exist."""
    for config_name in CONFIG_NAMES:
        try:
            if config_name.is_file():
                if config_name.suffix == ".toml" and not _toml_has_config(config_name):
                    continue
                if config_name.suffix == ".cfg" and not _cfg_has_config(config_name):
                    continue

                yield config_name.resolve()
        except OSError:
            pass


def _find_project_config() -> Iterator[Path]:
    """Traverse up the directory tree to find a config file.

    Stop if no '__init__' is found and thus we are no longer in a package.
    """
    if Path("__init__.py").is_file():
        curdir = Path(os.getcwd()).resolve()
        while (curdir / "__init__.py").is_file():
            curdir = curdir.parent
            for rc_name in RC_NAMES:
                rc_path = curdir / rc_name
                if rc_path.is_file():
                    yield rc_path.resolve()


def _find_config_in_home_or_environment() -> Iterator[Path]:
    """Find a config file in the specified environment var or the home directory."""
    if "PYLINTRC" in os.environ and Path(os.environ["PYLINTRC"]).exists():
        if Path(os.environ["PYLINTRC"]).is_file():
            yield Path(os.environ["PYLINTRC"]).resolve()
    else:
        try:
            user_home = Path.home()
        except RuntimeError:
            # If the home directory does not exist a RuntimeError will be raised
            user_home = None

        if user_home is not None and str(user_home) not in ("~", "/root"):
            home_rc = user_home / ".pylintrc"
            if home_rc.is_file():
                yield home_rc.resolve()

            home_rc = user_home / ".config" / "pylintrc"
            if home_rc.is_file():
                yield home_rc.resolve()


def find_default_config_files() -> Iterator[Path]:
    """Find all possible config files."""
    yield from _yield_default_files()

    try:
        yield from _find_project_config()
    except OSError:
        pass

    try:
        yield from _find_config_in_home_or_environment()
    except OSError:
        pass

    try:
        if os.path.isfile("/etc/pylintrc"):
            yield Path("/etc/pylintrc").resolve()
    except OSError:
        pass


def find_pylintrc() -> str | None:
    """Search the pylint rc file and return its path if it finds it, else return
    None.
    """
    # TODO: 3.0: Remove deprecated function
    warnings.warn(
        "find_pylintrc and the PYLINTRC constant have been deprecated. "
        "Use find_default_config_files if you want access to pylint's configuration file "
        "finding logic.",
        DeprecationWarning,
        stacklevel=2,
    )
    for config_file in find_default_config_files():
        if str(config_file).endswith("pylintrc"):
            return str(config_file)
    return None
