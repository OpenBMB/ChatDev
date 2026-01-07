"""Artifact event queue utilities used to expose workflow-produced files."""

import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence


@dataclass
class ArtifactEvent:
    """Represents a single file artifact surfaced to the frontend."""

    node_id: str
    attachment_id: str
    file_name: str
    relative_path: str
    workspace_path: str
    mime_type: Optional[str]
    size: Optional[int]
    sha256: Optional[str]
    data_uri: Optional[str]
    created_at: float = field(default_factory=lambda: time.time())
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    sequence: int = 0
    change_type: str = "created"
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "sequence": self.sequence,
            "node_id": self.node_id,
            "attachment_id": self.attachment_id,
            "file_name": self.file_name,
            "relative_path": self.relative_path,
            "workspace_path": self.workspace_path,
            "mime_type": self.mime_type,
            "size": self.size,
            "sha256": self.sha256,
            "data_uri": self.data_uri,
            "created_at": self.created_at,
            "change_type": self.change_type,
            "extra": self.extra,
        }

    def matches_filter(
        self,
        *,
        include_mime: Optional[Sequence[str]] = None,
        include_ext: Optional[Sequence[str]] = None,
        max_size: Optional[int] = None,
    ) -> bool:
        if max_size is not None and self.size is not None and self.size > max_size:
            return False

        if include_mime:
            mime = (self.mime_type or "").lower()
            if mime and any(mime.startswith(prefix.lower()) for prefix in include_mime):
                pass
            elif mime in (m.lower() for m in include_mime):
                pass
            else:
                return False

        if include_ext:
            suffix = Path(self.file_name).suffix.lower()
            if suffix.startswith("."):
                suffix = suffix[1:]
            include_ext_normalized = {ext.lower().lstrip(".") for ext in include_ext}
            if suffix not in include_ext_normalized:
                return False

        return True


class ArtifactEventQueue:
    """Thread-safe bounded queue that supports blocking waits."""

    def __init__(self, *, max_events: int = 2000) -> None:
        self._events: Deque[ArtifactEvent] = deque()
        self._condition = threading.Condition()
        self._max_events = max_events
        self._last_sequence = 0
        self._min_sequence = 1

    def append_many(self, events: Iterable[ArtifactEvent]) -> None:
        materialized = [event for event in events if event is not None]
        if not materialized:
            return
        with self._condition:
            for event in materialized:
                self._last_sequence += 1
                event.sequence = self._last_sequence
                self._events.append(event)
            while len(self._events) > self._max_events:
                self._events.popleft()
                self._min_sequence = max(self._min_sequence, self._last_sequence - len(self._events) + 1)
            self._condition.notify_all()

    def snapshot(
        self,
        *,
        after: Optional[int] = None,
        include_mime: Optional[Sequence[str]] = None,
        include_ext: Optional[Sequence[str]] = None,
        max_size: Optional[int] = None,
        limit: int = 50,
    ) -> tuple[List[ArtifactEvent], int]:
        limit = max(1, min(limit, 200))
        start_seq = after if after is not None else 0
        start_seq = max(start_seq, self._min_sequence - 1)

        events: List[ArtifactEvent] = []
        next_cursor = start_seq
        for event in self._events:
            if event.sequence <= start_seq:
                continue
            next_cursor = event.sequence
            if event.matches_filter(
                include_mime=include_mime,
                include_ext=include_ext,
                max_size=max_size,
            ):
                events.append(event)
                if len(events) >= limit:
                    break
        if next_cursor < start_seq:
            next_cursor = start_seq
        return events, next_cursor

    def wait_for_events(
        self,
        *,
        after: Optional[int],
        include_mime: Optional[Sequence[str]],
        include_ext: Optional[Sequence[str]],
        max_size: Optional[int],
        limit: int,
        timeout: float,
    ) -> tuple[List[ArtifactEvent], int, bool]:
        """Block until matching events appear or timeout expires.

        Returns (events, next_cursor, timeout_reached)
        """
        deadline = time.time() + max(0.0, timeout)
        with self._condition:
            events, next_cursor = self.snapshot(
                after=after,
                include_mime=include_mime,
                include_ext=include_ext,
                max_size=max_size,
                limit=limit,
            )
            while not events and time.time() < deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                self._condition.wait(timeout=remaining)
                events, next_cursor = self.snapshot(
                    after=after,
                    include_mime=include_mime,
                    include_ext=include_ext,
                    max_size=max_size,
                    limit=limit,
                )
            timed_out = not events
            return events, next_cursor or (after or 0), timed_out

    @property
    def last_sequence(self) -> int:
        return self._last_sequence
