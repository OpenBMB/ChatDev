"""Host-free serialization boundary for formal production metadata."""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Mapping, cast

from .path_policy import contains_private_host_locator, is_path_field_name


_SECRET_KEY = re.compile(
    r"(?i)^(?:api[_-]?key|authorization|password|secret|access[_-]?token|"
    r"refresh[_-]?token|bearer[_-]?token|credential)$"
)
_WRITE_LOCK = threading.RLock()


class FormalSerializationError(RuntimeError):
    """Raised before unsafe formal metadata can be persisted."""


def assert_formal_public_projection(
    value: object, *, locator: str = "event", path_context: bool = False
) -> None:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        for key, item in mapping.items():
            key_text = str(key)
            if (
                _SECRET_KEY.fullmatch(key_text)
                and item is not None
                and item != ""
                and item is not False
            ):
                raise FormalSerializationError(
                    f"secret_field_in_formal_projection:{locator}.{key_text}"
                )
            assert_formal_public_projection(
                item,
                locator=f"{locator}.{key_text}",
                # A path-typed list/scalar carries its field semantics into
                # its leaves.  Do not carry that context into an unrelated
                # metadata mapping: task text nested beside a path remains
                # task text, including Windows examples and LaTeX.
                path_context=is_path_field_name(key_text)
                or (path_context and not isinstance(item, Mapping)),
            )
        return
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        for index, item in enumerate(sequence):
            assert_formal_public_projection(
                item, locator=f"{locator}[{index}]", path_context=path_context
            )
        return
    if isinstance(value, Path):
        raise FormalSerializationError(f"path_object_in_formal_projection:{locator}")
    if isinstance(value, str) and path_context:
        if contains_private_host_locator(value):
            raise FormalSerializationError(f"host_path_in_formal_projection:{locator}")


def append_formal_jsonl(path: str | Path, event: Mapping[str, object]) -> None:
    payload = dict(event)
    assert_formal_public_projection(payload)
    try:
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise FormalSerializationError("formal_event_not_canonical_json") from exc
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with _WRITE_LOCK, target.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FormalSerializationError:
        raise
    except Exception as exc:
        raise FormalSerializationError("formal_event_append_failed") from exc


__all__ = [
    "FormalSerializationError",
    "append_formal_jsonl",
    "assert_formal_public_projection",
]
