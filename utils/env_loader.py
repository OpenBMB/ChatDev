"""Environment loading utilities for root-level vars interpolation."""


import os
from pathlib import Path
from typing import Dict

_DOTENV_LOADED = False


def load_dotenv_file(dotenv_path: Path | None = None) -> None:
    """Populate ``os.environ`` with key/value pairs from a .env file once per process."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return

    path = dotenv_path or Path(".env")
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

    _DOTENV_LOADED = True


def build_env_var_map(extra_vars: Dict[str, str] | None = None) -> Dict[str, str]:
    merged: Dict[str, str] = dict(os.environ)
    merged.update(extra_vars or {})
    return merged
