# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for the signal library.

The signal module generates the 'Signals', 'Handlers' and 'Sigmasks' IntEnums
dynamically using the IntEnum._convert() classmethod, which modifies the module
globals. Astroid is unable to handle this type of code.

Without these hooks, the following are erroneously triggered by Pylint:
    * E1101: Module 'signal' has no 'Signals' member (no-member)
    * E1101: Module 'signal' has no 'Handlers' member (no-member)
    * E1101: Module 'signal' has no 'Sigmasks' member (no-member)

These enums are defined slightly differently depending on the user's operating
system and platform. These platform differences should follow the current
Python typeshed stdlib `signal.pyi` stub file, available at:

* https://github.com/python/typeshed/blob/master/stdlib/signal.pyi

Note that the enum.auto() values defined here for the Signals, Handlers and
Sigmasks IntEnums are just dummy integer values, and do not correspond to the
actual standard signal numbers - which may vary depending on the system.
"""


import sys

from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.manager import AstroidManager


def _signals_enums_transform():
    """Generates the AST for 'Signals', 'Handlers' and 'Sigmasks' IntEnums."""
    return parse(_signals_enum() + _handlers_enum() + _sigmasks_enum())


def _signals_enum() -> str:
    """Generates the source code for the Signals int enum."""
    signals_enum = """
    import enum
    class Signals(enum.IntEnum):
        SIGABRT   = enum.auto()
        SIGEMT    = enum.auto()
        SIGFPE    = enum.auto()
        SIGILL    = enum.auto()
        SIGINFO   = enum.auto()
        SIGINT    = enum.auto()
        SIGSEGV   = enum.auto()
        SIGTERM   = enum.auto()
    """
    if sys.platform != "win32":
        signals_enum += """
        SIGALRM   = enum.auto()
        SIGBUS    = enum.auto()
        SIGCHLD   = enum.auto()
        SIGCONT   = enum.auto()
        SIGHUP    = enum.auto()
        SIGIO     = enum.auto()
        SIGIOT    = enum.auto()
        SIGKILL   = enum.auto()
        SIGPIPE   = enum.auto()
        SIGPROF   = enum.auto()
        SIGQUIT   = enum.auto()
        SIGSTOP   = enum.auto()
        SIGSYS    = enum.auto()
        SIGTRAP   = enum.auto()
        SIGTSTP   = enum.auto()
        SIGTTIN   = enum.auto()
        SIGTTOU   = enum.auto()
        SIGURG    = enum.auto()
        SIGUSR1   = enum.auto()
        SIGUSR2   = enum.auto()
        SIGVTALRM = enum.auto()
        SIGWINCH  = enum.auto()
        SIGXCPU   = enum.auto()
        SIGXFSZ   = enum.auto()
        """
    if sys.platform == "win32":
        signals_enum += """
        SIGBREAK  = enum.auto()
        """
    if sys.platform not in ("darwin", "win32"):
        signals_enum += """
        SIGCLD    = enum.auto()
        SIGPOLL   = enum.auto()
        SIGPWR    = enum.auto()
        SIGRTMAX  = enum.auto()
        SIGRTMIN  = enum.auto()
        """
    return signals_enum


def _handlers_enum() -> str:
    """Generates the source code for the Handlers int enum."""
    return """
    import enum
    class Handlers(enum.IntEnum):
        SIG_DFL = enum.auto()
        SIG_IGN = eunm.auto()
    """


def _sigmasks_enum() -> str:
    """Generates the source code for the Sigmasks int enum."""
    if sys.platform != "win32":
        return """
    import enum
    class Sigmasks(enum.IntEnum):
        SIG_BLOCK   = enum.auto()
        SIG_UNBLOCK = enum.auto()
        SIG_SETMASK = enum.auto()
        """
    return ""


register_module_extender(AstroidManager(), "signal", _signals_enums_transform)
