"""Standard-library checks; run with python -m unittest discover -s tests -p test_init_runtime_dirs.py."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.init_runtime_dirs import prepare_runtime_dirs, RUNTIME_DIRS


class RuntimeDirectoryTests(unittest.TestCase):
    def test_creates_storage_and_preserves_existing_files_on_repeat(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "data").mkdir()
            database = root / "data" / "existing.db"
            database.write_bytes(b"existing data")
            for _ in range(2):
                prepare_runtime_dirs(root, os.getuid(), os.getgid())
            self.assertEqual(database.read_bytes(), b"existing data")
            for name in RUNTIME_DIRS:
                self.assertTrue((root / name).is_dir())

    def test_does_not_chown_source_or_follow_artifact_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.py"
            source.write_text("unchanged")
            warehouse = root / "WareHouse"
            warehouse.mkdir()
            (warehouse / "file-link").symlink_to(source)
            (warehouse / "directory-link").symlink_to(root, target_is_directory=True)
            with patch("tools.init_runtime_dirs.os.chown") as chown:
                prepare_runtime_dirs(root, 1234, 1234)
            changed = {Path(call.args[0]) for call in chown.call_args_list}
            self.assertEqual(changed, {root / name for name in RUNTIME_DIRS})

    def test_rejects_symlinked_storage_root_before_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "data").symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                prepare_runtime_dirs(root, os.getuid(), os.getgid())
            self.assertFalse((root / "WareHouse").exists())
