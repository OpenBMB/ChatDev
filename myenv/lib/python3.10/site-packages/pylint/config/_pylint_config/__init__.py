# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Everything related to the 'pylint-config' command.

Everything in this module is private.
"""

from pylint.config._pylint_config.main import _handle_pylint_config_commands
from pylint.config._pylint_config.setup import _register_generate_config_options

__all__ = ("_handle_pylint_config_commands", "_register_generate_config_options")
