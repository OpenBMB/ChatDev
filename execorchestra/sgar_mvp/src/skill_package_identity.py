"""Cross-platform deterministic identity helpers for Skill packages."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Collection


IGNORED_SKILL_PACKAGE_PARTS = frozenset(
    {
        ".git",
        ".github",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
    }
)


class SkillPackagePathCollisionError(ValueError):
    """Raised when distinct package paths collide under case folding."""

    code = "skill_package_casefold_collision"

    def __init__(self, first: Path, second: Path):
        self.paths = (first.as_posix(), second.as_posix())
        super().__init__(f"{self.code}:{self.paths[0]}:{self.paths[1]}")


def skill_package_files(
    package_root: Path,
    ignored_parts: Collection[str] = IGNORED_SKILL_PACKAGE_PARTS,
) -> tuple[Path, ...]:
    """Return package files in a platform-independent component order."""

    ignored = {part.lower() for part in ignored_parts}
    entries: list[tuple[tuple[str, ...], tuple[str, ...], Path]] = []
    folded_paths: dict[tuple[str, ...], Path] = {}
    for path in package_root.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(package_root)
        if any(part.lower() in ignored for part in relative_path.parts):
            continue
        original_parts = tuple(relative_path.parts)
        folded_parts = tuple(part.casefold() for part in original_parts)
        previous = folded_paths.get(folded_parts)
        if previous is not None and tuple(previous.parts) != original_parts:
            raise SkillPackagePathCollisionError(previous, relative_path)
        folded_paths[folded_parts] = relative_path
        entries.append((folded_parts, original_parts, path))
    entries.sort(key=lambda item: (item[0], item[1]))
    return tuple(item[2] for item in entries)


def skill_package_fingerprint(
    package_root: Path,
    ignored_parts: Collection[str] = IGNORED_SKILL_PACKAGE_PARTS,
) -> tuple[str, int]:
    """Hash original-case POSIX paths and bytes using the sealed framing."""

    digest = hashlib.sha256()
    total_bytes = 0
    for path in skill_package_files(package_root, ignored_parts):
        relative = path.relative_to(package_root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
        total_bytes += len(data)
    return digest.hexdigest(), total_bytes
