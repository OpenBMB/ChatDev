"""Python Tool Configuration."""
from __future__ import annotations

from dataclasses import dataclass  # Backwards compatibility

from .fields import field
from .pytoolconfig import PyToolConfig
from .types import UniversalKey

__all__ = ["PyToolConfig", "field", "UniversalKey", "dataclass"]
