"""Resource coordination helpers for workflow node execution."""

import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from entity.configs import Node
from runtime.node.registry import get_node_registration
from utils.log_manager import LogManager


@dataclass(frozen=True, slots=True)
class ResourceRequest:
    """Represents a single resource requirement."""

    key: str
    limit: int


@dataclass(slots=True)
class _ResourceSlot:
    semaphore: threading.Semaphore
    limit: int


class ResourceManager:
    """Coordinates shared resource usage across nodes."""

    def __init__(self, log_manager: LogManager | None = None):
        self.log_manager = log_manager
        self._lock = threading.Lock()
        self._resources: Dict[str, _ResourceSlot] = {}

    @contextmanager
    def guard_node(self, node: Node):
        """Acquire all resources required by the given node."""
        requests = self._resolve_node_requests(node)
        with self._acquire_resources(requests):
            yield

    def _resolve_node_requests(self, node: Node) -> List[ResourceRequest]:
        registration = get_node_registration(node.node_type)
        caps = registration.capabilities
        requests: List[ResourceRequest] = []
        key = caps.resource_key
        limit = caps.resource_limit
        if key and limit and limit > 0:
            requests.append(ResourceRequest(key=key, limit=limit))
        return requests

    @contextmanager
    def _acquire_resources(self, requests: Iterable[ResourceRequest]):
        acquired: List[Tuple[str, threading.Semaphore]] = []
        try:
            for request in sorted(requests, key=lambda item: item.key):
                semaphore = self._get_or_create_resource(request)
                self._log_debug(f"Acquiring resource {request.key}")
                semaphore.acquire()
                acquired.append((request.key, semaphore))
            yield
        finally:
            for key, semaphore in reversed(acquired):
                semaphore.release()
                self._log_debug(f"Released resource {key}")

    def _get_or_create_resource(self, request: ResourceRequest) -> threading.Semaphore:
        with self._lock:
            slot = self._resources.get(request.key)
            if slot and slot.limit != request.limit:
                slot = None
            if not slot:
                slot = _ResourceSlot(
                    semaphore=threading.Semaphore(request.limit),
                    limit=request.limit,
                )
                self._resources[request.key] = slot
            return slot.semaphore

    def _log_debug(self, message: str) -> None:
        if self.log_manager:
            self.log_manager.debug(message)
