"""Prepare bind-mounted runtime storage for the non-root Docker backend."""

import os
from pathlib import Path
import pwd


RUNTIME_DIRS = ("WareHouse", "logs", "data")


def prepare_runtime_dirs(root: Path, uid: int, gid: int) -> None:
    # Reject redirected storage roots before making any changes. Never follow
    # links in generated artifacts into source files or other host directories.
    for name in RUNTIME_DIRS:
        if (root / name).is_symlink():
            raise ValueError(f"Runtime directory must not be a symlink: {root / name}")
    for name in RUNTIME_DIRS:
        directory = root / name
        directory.mkdir(parents=True, exist_ok=True)
        for current, _directories, files in os.walk(directory, followlinks=False):
            os.chown(current, uid, gid, follow_symlinks=False)
            for filename in files:
                path = Path(current) / filename
                if not path.is_symlink():
                    os.chown(path, uid, gid, follow_symlinks=False)
            # os.walk does not descend into symlinked directories.


if __name__ == "__main__":
    account = pwd.getpwnam("appuser")
    prepare_runtime_dirs(Path("/app"), account.pw_uid, account.pw_gid)
