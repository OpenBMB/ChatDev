from __future__ import annotations

from contextlib import contextmanager

from .base import AppData, ContentStore


class AppDataDisabled(AppData):
    """No application cache available (most likely as we don't have write permissions)"""

    transient = True
    can_update = False

    def __init__(self):
        pass

    error = RuntimeError("no app data folder available, probably no write access to the folder")

    def close(self):
        """do nothing"""

    def reset(self):
        """do nothing"""

    def py_info(self, path):  # noqa: U100
        return ContentStoreNA()

    def embed_update_log(self, distribution, for_py_version):  # noqa: U100
        return ContentStoreNA()

    def extract(self, path, to_folder):  # noqa: U100
        raise self.error

    @contextmanager
    def locked(self, path):  # noqa: U100
        """do nothing"""
        yield

    @property
    def house(self):
        raise self.error

    def wheel_image(self, for_py_version, name):  # noqa: U100
        raise self.error

    def py_info_clear(self):
        """nothing to clear"""


class ContentStoreNA(ContentStore):
    def exists(self):
        return False

    def read(self):
        """nothing to read"""
        return None

    def write(self, content):  # noqa: U100
        """nothing to write"""

    def remove(self):
        """nothing to remove"""

    @contextmanager
    def locked(self):
        yield


__all__ = [
    "AppDataDisabled",
    "ContentStoreNA",
]
