# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import contextlib
import sys
import traceback
import warnings
from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path

from pylint.config import PYLINT_HOME
from pylint.lint.expand_modules import discover_package_path


def prepare_crash_report(ex: Exception, filepath: str, crash_file_path: str) -> Path:
    issue_template_path = (
        Path(PYLINT_HOME) / datetime.now().strftime(str(crash_file_path))
    ).resolve()
    with open(filepath, encoding="utf8") as f:
        file_content = f.read()
    template = ""
    if not issue_template_path.exists():
        template = """\
First, please verify that the bug is not already filled:
https://github.com/PyCQA/pylint/issues/

Then create a new crash issue:
https://github.com/PyCQA/pylint/issues/new?assignees=&labels=crash%2Cneeds+triage&template=BUG-REPORT.yml

"""
    template += f"""\

Issue title:
Crash ``{ex}`` (if possible, be more specific about what made pylint crash)
Content:
When parsing the following file:

<!--
 If sharing the code is not an option, please state so,
 but providing only the stacktrace would still be helpful.
 -->

```python
{file_content}
```

pylint crashed with a ``{ex.__class__.__name__}`` and with the following stacktrace:
```
"""
    template += traceback.format_exc()
    template += "```\n"
    try:
        with open(issue_template_path, "a", encoding="utf8") as f:
            f.write(template)
    except Exception as exc:  # pylint: disable=broad-except
        print(
            f"Can't write the issue template for the crash in {issue_template_path} "
            f"because of: '{exc}'\nHere's the content anyway:\n{template}.",
            file=sys.stderr,
        )
    return issue_template_path


def get_fatal_error_message(filepath: str, issue_template_path: Path) -> str:
    return (
        f"Fatal error while checking '{filepath}'. "
        f"Please open an issue in our bug tracker so we address this. "
        f"There is a pre-filled template that you can use in '{issue_template_path}'."
    )


def _patch_sys_path(args: Sequence[str]) -> list[str]:
    # TODO: Remove deprecated function
    warnings.warn(
        "_patch_sys_path has been deprecated because it relies on auto-magic package path "
        "discovery which is implemented by get_python_path that is deprecated. "
        "Use _augment_sys_path and pass additional sys.path entries as an argument obtained from "
        "discover_package_path.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _augment_sys_path([discover_package_path(arg, []) for arg in args])


def _augment_sys_path(additional_paths: Sequence[str]) -> list[str]:
    original = list(sys.path)
    changes = []
    seen = set()
    for additional_path in additional_paths:
        if additional_path not in seen:
            changes.append(additional_path)
            seen.add(additional_path)

    sys.path[:] = changes + sys.path
    return original


@contextlib.contextmanager
def fix_import_path(args: Sequence[str]) -> Iterator[None]:
    """Prepare 'sys.path' for running the linter checks.

    Within this context, each of the given arguments is importable.
    Paths are added to 'sys.path' in corresponding order to the arguments.
    We avoid adding duplicate directories to sys.path.
    `sys.path` is reset to its original value upon exiting this context.
    """
    # TODO: Remove deprecated function
    warnings.warn(
        "fix_import_path has been deprecated because it relies on auto-magic package path "
        "discovery which is implemented by get_python_path that is deprecated. "
        "Use augmented_sys_path and pass additional sys.path entries as an argument obtained from "
        "discover_package_path.",
        DeprecationWarning,
        stacklevel=2,
    )
    with augmented_sys_path([discover_package_path(arg, []) for arg in args]):
        yield


@contextlib.contextmanager
def augmented_sys_path(additional_paths: Sequence[str]) -> Iterator[None]:
    """Augment 'sys.path' by adding non-existent entries from additional_paths."""
    original = _augment_sys_path(additional_paths)
    try:
        yield
    finally:
        sys.path[:] = original


def _is_relative_to(self: Path, *other: Path) -> bool:
    """Checks if self is relative to other.

    Backport of pathlib.Path.is_relative_to for Python <3.9
    TODO: py39: Remove this backport and use stdlib function.
    """
    try:
        self.relative_to(*other)
        return True
    except ValueError:
        return False
