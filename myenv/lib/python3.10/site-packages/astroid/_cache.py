# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from typing import Any


class CacheManager:
    """Manager of caches, to be used as a singleton."""

    def __init__(self) -> None:
        self.dict_caches: list[dict[Any, Any]] = []

    def clear_all_caches(self) -> None:
        """Clear all caches."""
        for dict_cache in self.dict_caches:
            dict_cache.clear()

    def add_dict_cache(self, cache: dict[Any, Any]) -> None:
        """Add a dictionary cache to the manager."""
        self.dict_caches.append(cache)


CACHE_MANAGER = CacheManager()
