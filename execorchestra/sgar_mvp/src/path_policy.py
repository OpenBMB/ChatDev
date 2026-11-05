"""Shared classification of private host locators versus semantic text.

Container paths (for example ``/app``), logical relative artifact names, and
domain text containing backslashes (LaTeX, regexes) are not private host
locators.  Windows drive paths, complete UNC paths, extended/device paths, and
``file:///`` URIs are.  Keep this module dependency-free so every formal
serialization boundary can use the same rule.
"""

from __future__ import annotations

import re


_TOKEN_BOUNDARY = r"(?:^|[\s'\"=(])"
WINDOWS_DRIVE_ABSOLUTE_RE = re.compile(
    _TOKEN_BOUNDARY + r"[A-Za-z]:[\\/]"
)
WINDOWS_EXTENDED_ABSOLUTE_RE = re.compile(
    _TOKEN_BOUNDARY + r"\\\\[?.]\\(?:UNC\\)?",
    re.IGNORECASE,
)
WINDOWS_UNC_ABSOLUTE_RE = re.compile(
    _TOKEN_BOUNDARY
    + r"\\\\[^\\/\s]+\\[^\\/\s]+",
    re.IGNORECASE,
)
FILE_URI_RE = re.compile(r"file:///", re.IGNORECASE)
PATH_FIELD_RE = re.compile(
    r"(?:^|_)(?:path|paths|cwd|directory|dir|uri|dispatch)$",
    re.IGNORECASE,
)


def is_path_field_name(name: object) -> bool:
    """Whether a mapping key carries a path/URI rather than task prose.

    This deliberately excludes generic keys such as ``text``, ``description``
    and ``source``.  A task is allowed to discuss Windows paths as data; only
    framework-owned path fields are subject to the Linux-only boundary.
    """

    key = str(name or "").strip()
    return bool(
        PATH_FIELD_RE.search(key)
        or key.lower() in {
            "path", "paths", "cwd", "working_directory", "host_path",
            "runtime_path", "source_path", "script_path", "file_path",
            "logical_path", "output_path", "input_path", "artifact_path",
            "dispatch", "uri", "project_root", "workspace_root", "runtime_root",
            "physical_root", "writable_root", "container_root",
        }
    )


def contains_private_host_locator(value: str) -> bool:
    """Return whether text contains a concrete private host locator.

    Two backslashes alone are deliberately insufficient: ``\\\\hbox`` and
    ``\\\\d+`` are valid LaTeX/regex text, whereas a UNC locator must include
    both a server and share component.
    """

    text = str(value or "")
    return bool(
        WINDOWS_DRIVE_ABSOLUTE_RE.search(text)
        or WINDOWS_EXTENDED_ABSOLUTE_RE.search(text)
        or WINDOWS_UNC_ABSOLUTE_RE.search(text)
        or FILE_URI_RE.search(text)
    )


def is_windows_absolute_path(value: str) -> bool:
    """Classify one path value, not arbitrary prose, as Windows-absolute."""

    text = str(value or "").strip()
    return bool(
        re.match(r"^[A-Za-z]:[\\/]", text)
        or re.match(r"^\\\\[?.]\\", text)
        or re.match(
            r"^\\\\[^\\/\s]+\\[^\\/\s]+",
            text,
        )
    )


def is_private_host_path_value(value: str) -> bool:
    """Classify a complete path-valued scalar, never arbitrary task prose."""

    text = str(value or "").strip()
    return is_windows_absolute_path(text) or bool(
        re.match(r"^file:///[^\s]+$", text, re.IGNORECASE)
    )


def assert_linux_control_path(value: object, *, field_name: str = "path") -> None:
    """Reject non-POSIX values in framework-owned path contracts.

    This applies only to fields declared as paths.  Windows paths in task
    prose or ordinary text arguments remain untouched.
    """

    if not isinstance(value, str):
        return
    text = value.strip()
    if "\\" in text or is_windows_absolute_path(text) or text.lower().startswith("file://"):
        raise ValueError(f"{field_name}_must_be_linux_posix_path")


__all__ = [
    "FILE_URI_RE",
    "WINDOWS_DRIVE_ABSOLUTE_RE",
    "WINDOWS_EXTENDED_ABSOLUTE_RE",
    "WINDOWS_UNC_ABSOLUTE_RE",
    "contains_private_host_locator",
    "is_windows_absolute_path",
    "is_private_host_path_value",
    "is_path_field_name",
    "assert_linux_control_path",
]
