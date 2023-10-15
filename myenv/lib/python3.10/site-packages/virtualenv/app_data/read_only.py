from __future__ import annotations

import os.path

from virtualenv.util.lock import NoOpFileLock

from .via_disk_folder import AppDataDiskFolder, PyInfoStoreDisk


class ReadOnlyAppData(AppDataDiskFolder):
    can_update = False

    def __init__(self, folder: str) -> None:
        if not os.path.isdir(folder):
            raise RuntimeError(f"read-only app data directory {folder} does not exist")
        super().__init__(folder)
        self.lock = NoOpFileLock(folder)

    def reset(self) -> None:
        raise RuntimeError("read-only app data does not support reset")

    def py_info_clear(self) -> None:
        raise NotImplementedError

    def py_info(self, path):
        return _PyInfoStoreDiskReadOnly(self.py_info_at, path)

    def embed_update_log(self, distribution, for_py_version):  # noqa: U100
        raise NotImplementedError


class _PyInfoStoreDiskReadOnly(PyInfoStoreDisk):
    def write(self, content):  # noqa: U100
        raise RuntimeError("read-only app data python info cannot be updated")


__all__ = [
    "ReadOnlyAppData",
]
