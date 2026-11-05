"""Safely extract one ZIP archive into an explicit task-workspace directory."""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath


MAX_MEMBERS = 10_000
MAX_UNCOMPRESSED_BYTES = 1_073_741_824


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def fail(message: str, code: int = 1) -> None:
    emit({"status": "error", "tool": "python-zipfile", "message": message})
    raise SystemExit(code)


def inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def normalized_member(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe archive member: {name!r}")
    return path


def main() -> int:
    if len(sys.argv) != 3:
        fail("usage: archive_zip_extract.py <archive_path> <output_directory>", 2)
    archive = Path(sys.argv[1]).resolve()
    destination = Path(sys.argv[2]).resolve()
    if not archive.is_file():
        fail("archive_path is not a readable file", 2)
    workspace_value = os.environ.get("SGAR_WORKSPACE_ROOT")
    if workspace_value:
        workspace = Path(workspace_value).resolve()
        if not inside(destination, workspace):
            fail("output_directory must remain within SGAR_WORKSPACE_ROOT", 2)
    try:
        with zipfile.ZipFile(archive) as source:
            members = source.infolist()
            if len(members) > MAX_MEMBERS:
                fail(f"archive exceeds {MAX_MEMBERS} members")
            total_bytes = sum(item.file_size for item in members)
            if total_bytes > MAX_UNCOMPRESSED_BYTES:
                fail(f"archive exceeds {MAX_UNCOMPRESSED_BYTES} uncompressed bytes")
            validated: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
            for member in members:
                relative = normalized_member(member.filename)
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    fail(f"symbolic-link archive member is unsupported: {member.filename!r}")
                target = (destination / Path(*relative.parts)).resolve()
                if not inside(target, destination):
                    fail(f"archive member escapes output_directory: {member.filename!r}")
                validated.append((member, relative))

            destination.mkdir(parents=True, exist_ok=True)
            extracted: list[str] = []
            for member, relative in validated:
                target = destination / Path(*relative.parts)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(member) as reader, target.open("wb") as writer:
                    shutil.copyfileobj(reader, writer)
                extracted.append(relative.as_posix())
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        fail(f"{type(exc).__name__}: {exc}")
    emit(
        {
            "status": "success",
            "tool": "python-zipfile",
            "extracted_files": extracted,
            "extracted_file_count": len(extracted),
            "total_uncompressed_bytes": total_bytes,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
