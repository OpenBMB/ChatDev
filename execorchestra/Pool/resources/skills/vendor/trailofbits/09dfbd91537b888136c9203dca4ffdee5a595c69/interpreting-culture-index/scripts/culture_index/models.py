"""Data models for Culture Index profile extraction."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExtractionResult:
    """Result of processing a single PDF."""

    pdf_name: str
    success: bool
    output_path: str | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
