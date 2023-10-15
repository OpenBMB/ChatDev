# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import warnings
from typing import Any

from pylint.config.option_manager_mixin import OptionsManagerMixIn
from pylint.config.options_provider_mixin import (  # type: ignore[attr-defined]
    OptionsProviderMixIn,
)


class ConfigurationMixIn(OptionsManagerMixIn, OptionsProviderMixIn):  # type: ignore[misc]
    """Basic mixin for simple configurations which don't need the
    manager / providers model.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # TODO: 3.0: Remove deprecated class
        warnings.warn(
            "ConfigurationMixIn has been deprecated and will be removed in pylint 3.0",
            DeprecationWarning,
            stacklevel=2,
        )
        if not args:
            kwargs.setdefault("usage", "")
        OptionsManagerMixIn.__init__(self, *args, **kwargs)
        OptionsProviderMixIn.__init__(self)
        if not getattr(self, "option_groups", None):
            self.option_groups: list[tuple[str, str]] = []
            for _, optdict in self.options:
                try:
                    gdef = (optdict["group"].upper(), "")
                except KeyError:
                    continue
                if gdef not in self.option_groups:
                    self.option_groups.append(gdef)
        self.register_options_provider(self, own_group=False)
