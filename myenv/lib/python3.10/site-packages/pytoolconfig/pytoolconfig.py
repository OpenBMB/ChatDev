"""Tool to configure Python tools."""
from __future__ import annotations

from argparse import SUPPRESS, ArgumentParser
from dataclasses import is_dataclass
from pathlib import Path
from typing import Generic, Sequence, TypeVar

from pytoolconfig.fields import _gather_config_fields
from pytoolconfig.sources import PyProject, PyTool, Source
from pytoolconfig.types import ConfigField, Dataclass
from pytoolconfig.universal_config import UniversalConfig
from pytoolconfig.utils import _dict_to_dataclass, _recursive_merge

DataclassT = TypeVar("DataclassT", bound=Dataclass)


class PyToolConfig(Generic[DataclassT]):
    """Python Tool Configuration Aggregator."""

    sources: list[Source] = []
    tool: str
    working_directory: Path
    model: type[DataclassT]
    fall_through: bool = False
    arg_parser: ArgumentParser | None = None
    _config_fields: dict[str, ConfigField]

    def __init__(
        self,
        tool: str,
        working_directory: Path,
        model: type[DataclassT],
        arg_parser: ArgumentParser | None = None,
        custom_sources: Sequence[Source] | None = None,
        global_config: bool = False,
        global_sources: Sequence[Source] | None = None,
        fall_through: bool = False,
        *args,
        **kwargs,
    ):
        """Initialize the configuration object.

        :param tool: name of the tool to use.
        :param working_directory: working directory in use.
        :param model: Model of configuration.
        :param arg_parser: Arugument Parser.
        :param custom_sources: Custom sources
        :param global_config: Enable global configuration
        :param global_sources: Custom global sources
        :param fall_through: Configuration options should fall through between sources.
        :param args: Passed to constructor for PyProject
        :param kwargs: Passed to constructor for PyProject
        """
        assert is_dataclass(model)
        self.model = model
        self._config_fields = _gather_config_fields(model)
        self.tool = tool
        self.sources = [PyProject(working_directory, tool, *args, **kwargs)]
        if custom_sources:
            self.sources.extend(custom_sources)
        if global_config:
            self.sources.append(PyTool(tool))
        if global_sources:
            self.sources.extend(global_sources)

        self.arg_parser = arg_parser
        self.fall_through = fall_through
        self._setup_arg_parser()

    def parse(self, args: list[str] | None = None) -> DataclassT:
        """Parse the configuration.

        :param args: any additional command line overwrites.
        """
        configuration = self._parse_sources()
        assert isinstance(self.sources[0], PyProject)
        universal: UniversalConfig = self.sources[0].universalconfig()
        if self.arg_parser:
            if args is None:
                args = []
            parsed = self.arg_parser.parse_args(args)
            for name, value in parsed._get_kwargs():
                setattr(configuration, name, value)
        for name, field in self._config_fields.items():
            if field.universal_config:
                universal_value = vars(universal)[field.universal_config.name]
                if universal_value is not None:
                    setattr(
                        configuration,
                        name,
                        universal_value,
                    )
        return configuration

    def _setup_arg_parser(self) -> None:
        if self.arg_parser:
            for name, field in self._config_fields.items():
                if field.command_line:
                    flags = field.command_line
                    self.arg_parser.add_argument(
                        *flags,
                        type=field._type,
                        help=field.description,
                        default=SUPPRESS,
                        metavar=name,
                        dest=name,
                    )

    def _parse_sources(self) -> DataclassT:
        configuration = self.model()
        if self.fall_through:
            for source in reversed(self.sources):
                parsed = source.parse()
                if parsed is not None:
                    configuration = _recursive_merge(configuration, parsed)

        else:
            for source in self.sources:
                parsed = source.parse()
                if parsed:
                    return _dict_to_dataclass(self.model, parsed)
        return configuration
