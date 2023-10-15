# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Arguments provider class used to expose options."""

from __future__ import annotations

import argparse
import optparse  # pylint: disable=deprecated-module
import warnings
from collections.abc import Iterator
from typing import Any

from pylint.config.arguments_manager import _ArgumentsManager
from pylint.typing import OptionDict, Options


class UnsupportedAction(Exception):
    """Raised by set_option when it doesn't know what to do for an action."""

    def __init__(self, *args: object) -> None:
        # TODO: 3.0: Remove deprecated exception
        warnings.warn(
            "UnsupportedAction has been deprecated and will be removed in pylint 3.0",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args)


class _ArgumentsProvider:
    """Base class for classes that provide arguments."""

    name: str
    """Name of the provider."""

    options: Options = ()
    """Options provided by this provider."""

    option_groups_descs: dict[str, str] = {}
    """Option groups of this provider and their descriptions."""

    def __init__(self, arguments_manager: _ArgumentsManager) -> None:
        self._arguments_manager = arguments_manager
        """The manager that will parse and register any options provided."""

        self._arguments_manager._register_options_provider(self)

        self._level = 0

    @property
    def level(self) -> int:
        # TODO: 3.0: Remove deprecated attribute
        warnings.warn(
            "The level attribute has been deprecated. It was used to display the checker in the help or not,"
            " and everything is displayed in the help now. It will be removed in pylint 3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._level

    @level.setter
    def level(self, value: int) -> None:
        # TODO: 3.0: Remove deprecated attribute
        warnings.warn(
            "Setting the level attribute has been deprecated. It was used to display the checker "
            "in the help or not, and everything is displayed in the help now. It will be removed "
            "in pylint 3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._level = value

    @property
    def config(self) -> argparse.Namespace:
        # TODO: 3.0: Remove deprecated attribute
        warnings.warn(
            "The checker-specific config attribute has been deprecated. Please use "
            "'linter.config' to access the global configuration object.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._arguments_manager.config

    def load_defaults(self) -> None:  # pragma: no cover
        """DEPRECATED: Initialize the provider using default values."""
        warnings.warn(
            "load_defaults has been deprecated. Option groups should be "
            "registered by initializing an ArgumentsProvider. "
            "This automatically registers the group on the ArgumentsManager.",
            DeprecationWarning,
            stacklevel=2,
        )
        for opt, optdict in self.options:
            action = optdict.get("action")
            if action != "callback":
                # callback action have no default
                if optdict is None:
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore", category=DeprecationWarning)
                        optdict = self.get_option_def(opt)
                default = optdict.get("default")
                self.set_option(opt, default, action, optdict)

    def option_attrname(
        self, opt: str, optdict: OptionDict | None = None
    ) -> str:  # pragma: no cover
        """DEPRECATED: Get the config attribute corresponding to opt."""
        warnings.warn(
            "option_attrname has been deprecated. It will be removed "
            "in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        if optdict is None:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                optdict = self.get_option_def(opt)
        return optdict.get("dest", opt.replace("-", "_"))  # type: ignore[return-value]

    def option_value(self, opt: str) -> Any:  # pragma: no cover
        """DEPRECATED: Get the current value for the given option."""
        warnings.warn(
            "option_value has been deprecated. It will be removed "
            "in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(self._arguments_manager.config, opt.replace("-", "_"), None)

    def set_option(  # pragma: no cover
        self,
        optname: Any,
        value: Any,
        action: Any = None,  # pylint: disable=unused-argument
        optdict: Any = None,  # pylint: disable=unused-argument
    ) -> None:
        """DEPRECATED: Method called to set an option (registered in the options
        list).
        """
        # TODO: 3.0: Remove deprecated method.
        warnings.warn(
            "set_option has been deprecated. You can use _arguments_manager.set_option "
            "or linter.set_option to set options on the global configuration object.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._arguments_manager.set_option(optname, value)

    def get_option_def(self, opt: str) -> OptionDict:  # pragma: no cover
        """DEPRECATED: Return the dictionary defining an option given its name.

        :raises OptionError: If the option isn't found.
        """
        warnings.warn(
            "get_option_def has been deprecated. It will be removed "
            "in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        assert self.options
        for option in self.options:
            if option[0] == opt:
                return option[1]
        raise optparse.OptionError(
            f"no such option {opt} in section {self.name!r}", opt  # type: ignore[arg-type]
        )

    def options_by_section(
        self,
    ) -> Iterator[
        tuple[str, list[tuple[str, OptionDict, Any]]]
        | tuple[None, dict[str, list[tuple[str, OptionDict, Any]]]]
    ]:  # pragma: no cover
        """DEPRECATED: Return an iterator on options grouped by section.

        (section, [list of (optname, optdict, optvalue)])
        """
        # TODO 3.0: Make this function private see
        # https://github.com/PyCQA/pylint/pull/6665#discussion_r880143229
        # It's only used in '_get_global_options_documentation'
        warnings.warn(
            "options_by_section has been deprecated. It will be removed "
            "in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        sections: dict[str, list[tuple[str, OptionDict, Any]]] = {}
        for optname, optdict in self.options:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                sections.setdefault(optdict.get("group"), []).append(  # type: ignore[arg-type]
                    (optname, optdict, self.option_value(optname))
                )
        if None in sections:
            yield None, sections.pop(None)  # type: ignore[call-overload]
        for section, options in sorted(sections.items()):
            yield section.upper(), options

    def options_and_values(
        self, options: Options | None = None
    ) -> Iterator[tuple[str, OptionDict, Any]]:  # pragma: no cover
        """DEPRECATED."""
        warnings.warn(
            "options_and_values has been deprecated. It will be removed "
            "in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        if options is None:
            options = self.options
        for optname, optdict in options:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                yield optname, optdict, self.option_value(optname)
