"""Content facts from actual bytes, independent of file names and task wording."""
from pathlib import Path


def is_utf8_file(path: Path) -> bool:
    """Check the complete file using bounded memory, without an input-size cap."""
    try:
        with path.open("r", encoding="utf-8", errors="strict") as stream:
            while stream.read(65536):
                pass
    except UnicodeError:
        return False
    return True
