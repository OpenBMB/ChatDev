"""Read-only container structure observations, never inferred task facts."""
from pathlib import Path
import zipfile

from .execution_contracts import infer_artifact_type_from_path


def observe_container_inventory(path: Path, *, extension: str) -> dict:
    # Office documents are ZIP-based too; only an explicitly supplied archive
    # gets container semantics. No extraction or member content is performed.
    if extension.lower() != ".zip":
        return {}
    try:
        with zipfile.ZipFile(path) as archive:
            entries = [entry for entry in archive.infolist() if not entry.is_dir()]
            members = [{"member_name": entry.filename,
                        "format_id": Path(entry.filename).suffix.lower().lstrip("."),
                        "artifact_type": infer_artifact_type_from_path(entry.filename, default="file"),
                        "byte_size": entry.file_size, "encrypted": bool(entry.flag_bits & 1)}
                       for entry in entries]
        return {"protocol": "sgar-container-inventory-v1", "format": "zip",
                "status": "observed", "member_count": len(members),
                "members": members[:64], "members_complete": len(members) <= 64,
                "artifact_types": sorted({entry["artifact_type"] for entry in members}),
                "formats": sorted({entry["format_id"] for entry in members if entry["format_id"]}),
                "content_observed": False}
    except (OSError, zipfile.BadZipFile, ValueError):
        return {"protocol": "sgar-container-inventory-v1", "format": "zip",
                "status": "unavailable", "content_observed": False}
