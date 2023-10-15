# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Functions that creates the basic options for the Run and PyLinter classes."""

from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

from pylint import constants, interfaces
from pylint.config.callback_actions import (
    _DisableAction,
    _DoNothingAction,
    _EnableAction,
    _ErrorsOnlyModeAction,
    _FullDocumentationAction,
    _GenerateConfigFileAction,
    _GenerateRCFileAction,
    _ListCheckGroupsAction,
    _ListConfidenceLevelsAction,
    _ListExtensionsAction,
    _ListMessagesAction,
    _ListMessagesEnabledAction,
    _LongHelpAction,
    _MessageHelpAction,
    _OutputFormatAction,
)
from pylint.typing import Options

if TYPE_CHECKING:
    from pylint.lint import PyLinter, Run


def _make_linter_options(linter: PyLinter) -> Options:
    """Return the options used in a PyLinter class."""
    return (
        (
            "ignore",
            {
                "type": "csv",
                "metavar": "<file>[,<file>...]",
                "dest": "black_list",
                "kwargs": {"old_names": ["black_list"]},
                "default": constants.DEFAULT_IGNORE_LIST,
                "help": "Files or directories to be skipped. "
                "They should be base names, not paths.",
            },
        ),
        (
            "ignore-patterns",
            {
                "type": "regexp_csv",
                "metavar": "<pattern>[,<pattern>...]",
                "dest": "black_list_re",
                "default": (re.compile(r"^\.#"),),
                "help": "Files or directories matching the regular expression patterns are"
                " skipped. The regex matches against base names, not paths. The default value "
                "ignores Emacs file locks",
            },
        ),
        (
            "ignore-paths",
            {
                "type": "regexp_paths_csv",
                "metavar": "<pattern>[,<pattern>...]",
                "default": [],
                "help": "Add files or directories matching the regular expressions patterns to the "
                "ignore-list. The regex matches against paths and can be in "
                "Posix or Windows format. Because '\\\\' represents the directory delimiter "
                "on Windows systems, it can't be used as an escape character.",
            },
        ),
        (
            "persistent",
            {
                "default": True,
                "type": "yn",
                "metavar": "<y or n>",
                "help": "Pickle collected data for later comparisons.",
            },
        ),
        (
            "load-plugins",
            {
                "type": "csv",
                "metavar": "<modules>",
                "default": (),
                "help": "List of plugins (as comma separated values of "
                "python module names) to load, usually to register "
                "additional checkers.",
            },
        ),
        (
            "output-format",
            {
                "default": "text",
                "action": _OutputFormatAction,
                "callback": lambda x: x,
                "metavar": "<format>",
                "short": "f",
                "group": "Reports",
                "help": "Set the output format. Available formats are text,"
                " parseable, colorized, json and msvs (visual studio)."
                " You can also give a reporter class, e.g. mypackage.mymodule."
                "MyReporterClass.",
                "kwargs": {"linter": linter},
            },
        ),
        (
            "reports",
            {
                "default": False,
                "type": "yn",
                "metavar": "<y or n>",
                "short": "r",
                "group": "Reports",
                "help": "Tells whether to display a full report or only the "
                "messages.",
            },
        ),
        (
            "evaluation",
            {
                "type": "string",
                "metavar": "<python_expression>",
                "group": "Reports",
                "default": "max(0, 0 if fatal else 10.0 - ((float(5 * error + warning + refactor + "
                "convention) / statement) * 10))",
                "help": "Python expression which should return a score less "
                "than or equal to 10. You have access to the variables 'fatal', "
                "'error', 'warning', 'refactor', 'convention', and 'info' which "
                "contain the number of messages in each category, as well as "
                "'statement' which is the total number of statements "
                "analyzed. This score is used by the global "
                "evaluation report (RP0004).",
            },
        ),
        (
            "score",
            {
                "default": True,
                "type": "yn",
                "metavar": "<y or n>",
                "short": "s",
                "group": "Reports",
                "help": "Activate the evaluation score.",
            },
        ),
        (
            "fail-under",
            {
                "default": 10,
                "type": "float",
                "metavar": "<score>",
                "help": "Specify a score threshold under which the program will exit with error.",
            },
        ),
        (
            "fail-on",
            {
                "default": "",
                "type": "csv",
                "metavar": "<msg ids>",
                "help": "Return non-zero exit code if any of these messages/categories are detected,"
                " even if score is above --fail-under value. Syntax same as enable."
                " Messages specified are enabled, while categories only check already-enabled messages.",
            },
        ),
        (
            "confidence",
            {
                "type": "confidence",
                "metavar": "<levels>",
                "default": interfaces.CONFIDENCE_LEVEL_NAMES,
                "group": "Messages control",
                "help": "Only show warnings with the listed confidence levels."
                f" Leave empty to show all. Valid levels: {', '.join(interfaces.CONFIDENCE_LEVEL_NAMES)}.",
            },
        ),
        (
            "enable",
            {
                "action": _EnableAction,
                "callback": lambda x1, x2, x3, x4: x1,
                "default": (),
                "metavar": "<msg ids>",
                "short": "e",
                "group": "Messages control",
                "help": "Enable the message, report, category or checker with the "
                "given id(s). You can either give multiple identifier "
                "separated by comma (,) or put this option multiple time "
                "(only on the command line, not in the configuration file "
                "where it should appear only once). "
                'See also the "--disable" option for examples.',
                "kwargs": {"linter": linter},
            },
        ),
        (
            "disable",
            {
                "action": _DisableAction,
                "callback": lambda x1, x2, x3, x4: x1,
                "metavar": "<msg ids>",
                "default": (),
                "short": "d",
                "group": "Messages control",
                "help": "Disable the message, report, category or checker "
                "with the given id(s). You can either give multiple identifiers "
                "separated by comma (,) or put this option multiple times "
                "(only on the command line, not in the configuration file "
                "where it should appear only once). "
                'You can also use "--disable=all" to disable everything first '
                "and then re-enable specific checks. For example, if you want "
                "to run only the similarities checker, you can use "
                '"--disable=all --enable=similarities". '
                "If you want to run only the classes checker, but have no "
                "Warning level messages displayed, use "
                '"--disable=all --enable=classes --disable=W".',
                "kwargs": {"linter": linter},
            },
        ),
        (
            "msg-template",
            {
                "type": "string",
                "default": "",
                "metavar": "<template>",
                "group": "Reports",
                "help": (
                    "Template used to display messages. "
                    "This is a python new-style format string "
                    "used to format the message information. "
                    "See doc for all details."
                ),
            },
        ),
        (
            "jobs",
            {
                "type": "int",
                "metavar": "<n-processes>",
                "short": "j",
                "default": 1,
                "help": "Use multiple processes to speed up Pylint. Specifying 0 will "
                "auto-detect the number of processors available to use, and will cap "
                "the count on Windows to avoid hangs.",
            },
        ),
        (
            "unsafe-load-any-extension",
            {
                "type": "yn",
                "metavar": "<y or n>",
                "default": False,
                "hide": True,
                "help": (
                    "Allow loading of arbitrary C extensions. Extensions"
                    " are imported into the active Python interpreter and"
                    " may run arbitrary code."
                ),
            },
        ),
        (
            "limit-inference-results",
            {
                "type": "int",
                "metavar": "<number-of-results>",
                "default": 100,
                "help": (
                    "Control the amount of potential inferred values when inferring "
                    "a single object. This can help the performance when dealing with "
                    "large functions or complex, nested conditions."
                ),
            },
        ),
        (
            "extension-pkg-allow-list",
            {
                "type": "csv",
                "metavar": "<pkg[,pkg]>",
                "default": [],
                "help": (
                    "A comma-separated list of package or module names"
                    " from where C extensions may be loaded. Extensions are"
                    " loading into the active Python interpreter and may run"
                    " arbitrary code."
                ),
            },
        ),
        (
            "extension-pkg-whitelist",
            {
                "type": "csv",
                "metavar": "<pkg[,pkg]>",
                "default": [],
                "help": (
                    "A comma-separated list of package or module names"
                    " from where C extensions may be loaded. Extensions are"
                    " loading into the active Python interpreter and may run"
                    " arbitrary code. (This is an alternative name to"
                    " extension-pkg-allow-list for backward compatibility.)"
                ),
            },
        ),
        (
            "suggestion-mode",
            {
                "type": "yn",
                "metavar": "<y or n>",
                "default": True,
                "help": (
                    "When enabled, pylint would attempt to guess common "
                    "misconfiguration and emit user-friendly hints instead "
                    "of false-positive error messages."
                ),
            },
        ),
        (
            "exit-zero",
            {
                "action": "store_true",
                "default": False,
                "metavar": "<flag>",
                "help": (
                    "Always return a 0 (non-error) status code, even if "
                    "lint errors are found. This is primarily useful in "
                    "continuous integration scripts."
                ),
            },
        ),
        (
            "from-stdin",
            {
                "action": "store_true",
                "default": False,
                "metavar": "<flag>",
                "help": (
                    "Interpret the stdin as a python script, whose filename "
                    "needs to be passed as the module_or_package argument."
                ),
            },
        ),
        (
            "source-roots",
            {
                "type": "glob_paths_csv",
                "metavar": "<path>[,<path>...]",
                "default": (),
                "help": "Add paths to the list of the source roots. Supports globbing patterns. "
                "The source root is an absolute path or a path relative to the current working "
                "directory used to determine a package namespace for modules located under the "
                "source root.",
            },
        ),
        (
            "recursive",
            {
                "type": "yn",
                "metavar": "<yn>",
                "default": False,
                "help": "Discover python modules and packages in the file system subtree.",
            },
        ),
        (
            "py-version",
            {
                "default": sys.version_info[:2],
                "type": "py_version",
                "metavar": "<py_version>",
                "help": (
                    "Minimum Python version to use for version dependent checks. "
                    "Will default to the version used to run pylint."
                ),
            },
        ),
        (
            "ignored-modules",
            {
                "default": (),
                "type": "csv",
                "metavar": "<module names>",
                "help": "List of module names for which member attributes "
                "should not be checked (useful for modules/projects "
                "where namespaces are manipulated during runtime and "
                "thus existing member attributes cannot be "
                "deduced by static analysis). It supports qualified "
                "module names, as well as Unix pattern matching.",
            },
        ),
        (
            "analyse-fallback-blocks",
            {
                "default": False,
                "type": "yn",
                "metavar": "<y or n>",
                "help": "Analyse import fallback blocks. This can be used to "
                "support both Python 2 and 3 compatible code, which "
                "means that the block might have code that exists "
                "only in one or another interpreter, leading to false "
                "positives when analysed.",
            },
        ),
        (
            "clear-cache-post-run",
            {
                "default": False,
                "type": "yn",
                "metavar": "<y or n>",
                "help": "Clear in-memory caches upon conclusion of linting. "
                "Useful if running pylint in a server-like mode.",
            },
        ),
    )


def _make_run_options(self: Run) -> Options:
    """Return the options used in a Run class."""
    return (
        (
            "rcfile",
            {
                "action": _DoNothingAction,
                "kwargs": {},
                "group": "Commands",
                "help": "Specify a configuration file to load.",
                "hide_from_config_file": True,
            },
        ),
        (
            "output",
            {
                "action": _DoNothingAction,
                "kwargs": {},
                "group": "Commands",
                "help": "Specify an output file.",
                "hide_from_config_file": True,
            },
        ),
        (
            "init-hook",
            {
                "action": _DoNothingAction,
                "kwargs": {},
                "help": "Python code to execute, usually for sys.path "
                "manipulation such as pygtk.require().",
            },
        ),
        (
            "help-msg",
            {
                "action": _MessageHelpAction,
                "kwargs": {"Run": self},
                "group": "Commands",
                "help": "Display a help message for the given message id and "
                "exit. The value may be a comma separated list of message ids.",
                "hide_from_config_file": True,
            },
        ),
        (
            "list-msgs",
            {
                "action": _ListMessagesAction,
                "kwargs": {"Run": self},
                "group": "Commands",
                "help": "Display a list of all pylint's messages divided by whether "
                "they are emittable with the given interpreter.",
                "hide_from_config_file": True,
            },
        ),
        (
            "list-msgs-enabled",
            {
                "action": _ListMessagesEnabledAction,
                "kwargs": {"Run": self},
                "group": "Commands",
                "help": "Display a list of what messages are enabled, "
                "disabled and non-emittable with the given configuration.",
                "hide_from_config_file": True,
            },
        ),
        (
            "list-groups",
            {
                "action": _ListCheckGroupsAction,
                "kwargs": {"Run": self},
                "group": "Commands",
                "help": "List pylint's message groups.",
                "hide_from_config_file": True,
            },
        ),
        (
            "list-conf-levels",
            {
                "action": _ListConfidenceLevelsAction,
                "kwargs": {"Run": self},
                "group": "Commands",
                "help": "Generate pylint's confidence levels.",
                "hide_from_config_file": True,
            },
        ),
        (
            "list-extensions",
            {
                "action": _ListExtensionsAction,
                "kwargs": {"Run": self},
                "group": "Commands",
                "help": "List available extensions.",
                "hide_from_config_file": True,
            },
        ),
        (
            "full-documentation",
            {
                "action": _FullDocumentationAction,
                "kwargs": {"Run": self},
                "group": "Commands",
                "help": "Generate pylint's full documentation.",
                "hide_from_config_file": True,
            },
        ),
        (
            "generate-rcfile",
            {
                "action": _GenerateRCFileAction,
                "kwargs": {"Run": self},
                "group": "Commands",
                "help": "Generate a sample configuration file according to "
                "the current configuration. You can put other options "
                "before this one to get them in the generated "
                "configuration.",
                "hide_from_config_file": True,
            },
        ),
        (
            "generate-toml-config",
            {
                "action": _GenerateConfigFileAction,
                "kwargs": {"Run": self},
                "group": "Commands",
                "help": "Generate a sample configuration file according to "
                "the current configuration. You can put other options "
                "before this one to get them in the generated "
                "configuration. The config is in the .toml format.",
                "hide_from_config_file": True,
            },
        ),
        (
            "errors-only",
            {
                "action": _ErrorsOnlyModeAction,
                "kwargs": {"Run": self},
                "short": "E",
                "help": "In error mode, messages with a category besides "
                "ERROR or FATAL are suppressed, and no reports are done by default. "
                "Error mode is compatible with disabling specific errors. ",
                "hide_from_config_file": True,
            },
        ),
        (
            "verbose",
            {
                "action": _DoNothingAction,
                "kwargs": {},
                "short": "v",
                "help": "In verbose mode, extra non-checker-related info "
                "will be displayed.",
                "hide_from_config_file": True,
                "metavar": "",
            },
        ),
        (
            "enable-all-extensions",
            {
                "action": _DoNothingAction,
                "kwargs": {},
                "help": "Load and enable all available extensions. "
                "Use --list-extensions to see a list all available extensions.",
                "hide_from_config_file": True,
                "metavar": "",
            },
        ),
        (
            "long-help",
            {
                "action": _LongHelpAction,
                "kwargs": {"Run": self},
                "help": "Show more verbose help.",
                "group": "Commands",
                "hide_from_config_file": True,
            },
        ),
    )
