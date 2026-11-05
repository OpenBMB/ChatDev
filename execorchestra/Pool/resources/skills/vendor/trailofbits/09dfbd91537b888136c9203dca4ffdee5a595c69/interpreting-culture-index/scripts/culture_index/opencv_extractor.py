"""OpenCV-based extraction for Culture Index profiles.

Uses HSV color detection, shape analysis, and OCR to extract trait values,
arrow positions, and EU values from Culture Index PDF charts.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict

import cv2
import numpy as np
from pdf2image import convert_from_path

from culture_index.constants import (
    ARCHETYPES,
    OPENCV_A_MIN_AREA,
    OPENCV_ARCHETYPE_REGION_Y_END,
    OPENCV_ARROW_AREA_MAX,
    OPENCV_ARROW_AREA_MIN,
    OPENCV_ARROW_ASPECT_MAX,
    OPENCV_ARROW_HUE_HIGH,
    OPENCV_ARROW_HUE_LOW,
    OPENCV_ARROW_MIN_HEIGHT,
    OPENCV_ARROW_SAT_MIN,
    OPENCV_ARROW_VAL_MIN,
    OPENCV_CHART_X_END,
    OPENCV_CHART_X_START,
    OPENCV_COMPANY_REGION_Y_END,
    OPENCV_DOT_AREA_MAX,
    OPENCV_DOT_AREA_MIN,
    OPENCV_DOT_ASPECT_MAX,
    OPENCV_DOT_ASPECT_MIN,
    OPENCV_EU_REGION_X_END,
    OPENCV_EU_REGION_X_START,
    OPENCV_HEADER_DOT_Y_MAX,
    OPENCV_HUE_A_HIGH,
    OPENCV_HUE_A_LOW,
    OPENCV_HUE_B_MAX,
    OPENCV_HUE_B_MIN,
    OPENCV_HUE_C_MAX,
    OPENCV_HUE_C_MIN,
    OPENCV_HUE_D_MAX,
    OPENCV_HUE_D_MIN,
    OPENCV_HUE_I_MIN,
    OPENCV_HUE_L_MAX,
    OPENCV_HUE_L_MIN,
    OPENCV_JOB_Y_END,
    OPENCV_JOB_Y_START,
    OPENCV_METADATA_X_START,
    OPENCV_METADATA_Y_END,
    OPENCV_METADATA_Y_START,
    OPENCV_MIN_CONTOUR_AREA,
    OPENCV_NAME_REGION_Y_END,
    OPENCV_SATURATION_MIN,
    OPENCV_SURVEY_Y_END,
    OPENCV_SURVEY_Y_START,
    OPENCV_VALUE_MIN,
)

# Check pytesseract availability at module load
try:
    import pytesseract

    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    pytesseract = None  # type: ignore[assignment]

# Track extraction warnings for reporting
_extraction_warnings: list[str] = []


def get_extraction_warnings() -> list[str]:
    """Get warnings accumulated during extraction.

    Returns:
        List of warning messages from the last extraction.
    """
    return _extraction_warnings.copy()


def clear_extraction_warnings() -> None:
    """Clear accumulated extraction warnings."""
    _extraction_warnings.clear()


class DotData(TypedDict):
    """Data for a detected trait dot."""

    x: int
    y: int
    area: float
    hue: int


class ArrowData(TypedDict):
    """Data for a detected arrow (population mean indicator)."""

    x: int
    y: int
    w: int
    h: int
    area: float


def pixel_to_scale(x: int, x_start: int, x_end: int, as_float: bool = False) -> int | float:
    """Convert x pixel coordinate to 0-10 scale value.

    Args:
        x: X coordinate in pixels.
        x_start: X coordinate for position 0.
        x_end: X coordinate for position 10.
        as_float: If True, return tenths precision for arrows.

    Returns:
        Scale value 0-10 (int when as_float=False, float when as_float=True).
    """
    relative = (x - x_start) / (x_end - x_start)
    if as_float:
        return round(max(0.0, min(10.0, relative * 10)), 1)
    return max(0, min(10, round(relative * 10)))


def _extract_text_from_region(img_rgb: np.ndarray, region: tuple[int, int, int, int]) -> str:
    """Extract text from a region using OCR.

    Args:
        img_rgb: RGB image array.
        region: (x1, y1, x2, y2) bounding box.

    Returns:
        Extracted text, or empty string if OCR unavailable or fails.
    """
    if not PYTESSERACT_AVAILABLE:
        if "pytesseract not installed" not in str(_extraction_warnings):
            _extraction_warnings.append(
                "pytesseract not installed - text extraction disabled. "
                "Install with: pip install pytesseract && brew install tesseract"
            )
        return ""

    x1, y1, x2, y2 = region
    roi = img_rgb[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
    return pytesseract.image_to_string(gray, config="--psm 6")


def _extract_eu(img_rgb: np.ndarray, region: tuple[int, int, int, int]) -> int | None:
    """Extract EU value from a region using OCR.

    Args:
        img_rgb: RGB image array.
        region: (x1, y1, x2, y2) bounding box.

    Returns:
        EU value as integer, or None if not found.
    """
    text = _extract_text_from_region(img_rgb, region)
    if not text:
        return None
    match = re.search(r"EU\s*=?\s*(\d+)", text)
    return int(match.group(1)) if match else None


def _is_valid_name(text: str) -> bool:
    """Check if text looks like a person's name (2-4 words).

    Args:
        text: Candidate name string.

    Returns:
        True if text appears to be a valid name.
    """
    words = text.split()
    if not (2 <= len(words) <= 4):
        return False
    for word in words:
        cleaned = word.replace("'", "").replace("-", "")
        if not cleaned or not cleaned.isalpha():
            return False
    return True


def _clean_ocr_value(value: str, field_key: str) -> str:
    """Clean common OCR artifacts from metadata values.

    Args:
        value: Raw OCR value.
        field_key: The field key (email, phone, etc.) for field-specific cleanup.

    Returns:
        Cleaned value string.
    """
    value = value.lstrip("| ")
    if field_key == "email":
        value = re.sub(r"\s+@", "@", value)
    return value.strip()


def _parse_metadata_column(text: str) -> dict[str, str]:
    """Parse structured metadata from right column text.

    Args:
        text: Raw OCR text from metadata column.

    Returns:
        Dict with parsed metadata fields.
    """
    result: dict[str, str] = {}
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    field_mapping = {
        "survey date": "date",
        "email": "email",
        "phone": "phone",
        "job title": "job_title",
        "location": "location",
        "administered by": "administered_by",
        "survey type": "survey_type",
        "survey id": "survey_id",
    }

    i = 0
    while i < len(lines) - 1:
        line_lower = lines[i].lower()
        for label, key in field_mapping.items():
            if label in line_lower:
                value = lines[i + 1].strip()
                if value and not any(lbl in value.lower() for lbl in field_mapping):
                    result[key] = _clean_ocr_value(value, key)
                i += 1
                break
        i += 1

    return result


def _parse_name_from_filename(stem: str) -> str:
    """Parse person's name from PDF filename.

    Args:
        stem: PDF filename without extension.

    Returns:
        Parsed name string.
    """
    match = re.match(r"^(.+?)_\((\d+)\)$", stem)
    if match:
        return match.group(1).replace("_", " ")
    return stem


def _extract_header_info(img_rgb: np.ndarray, height: int, width: int) -> dict[str, str]:
    """Extract name, archetype, company, and all metadata from landscape layout.

    Args:
        img_rgb: RGB image array.
        height: Image height in pixels.
        width: Image width in pixels.

    Returns:
        Dict with extracted header info and metadata.
    """
    result: dict[str, str] = {}

    # Name: top-left corner
    name_region = (0, 0, int(width * 0.5), int(height * OPENCV_NAME_REGION_Y_END))
    name_text = _extract_text_from_region(img_rgb, name_region)
    if name_text:
        for line in name_text.split("\n"):
            line = line.strip()
            if line and _is_valid_name(line):
                result["name"] = line.title()
                break

    # Company: below name
    company_region = (
        0,
        int(height * OPENCV_NAME_REGION_Y_END),
        int(width * 0.5),
        int(height * OPENCV_COMPANY_REGION_Y_END),
    )
    company_text = _extract_text_from_region(img_rgb, company_region)
    if company_text:
        company_line = company_text.strip().split("\n")[0].strip()
        company_line = _clean_ocr_value(company_line, "company")
        if company_line and len(company_line) > 1:
            result["company"] = company_line

    # Archetype: below company
    archetype_region = (
        0,
        int(height * OPENCV_COMPANY_REGION_Y_END),
        int(width * 0.5),
        int(height * OPENCV_ARCHETYPE_REGION_Y_END),
    )
    archetype_text = _extract_text_from_region(img_rgb, archetype_region)
    for archetype in ARCHETYPES:
        if archetype.upper() in archetype_text.upper():
            result["archetype"] = archetype
            break

    # Metadata column (right side)
    metadata_region = (
        int(width * OPENCV_METADATA_X_START),
        int(height * OPENCV_METADATA_Y_START),
        width,
        int(height * OPENCV_METADATA_Y_END),
    )
    metadata_text = _extract_text_from_region(img_rgb, metadata_region)
    result.update(_parse_metadata_column(metadata_text))

    return result


def _classify_contour(
    contour: np.ndarray, img_hsv: np.ndarray
) -> tuple[str | None, DotData | ArrowData | dict[str, object]]:
    """Classify a contour as dot, arrow, or noise.

    Args:
        contour: OpenCV contour.
        img_hsv: HSV image array.

    Returns:
        Tuple of (type, data) where type is "dot", "arrow", or None.
        Data is DotData for dots, ArrowData for arrows, empty dict for noise.
    """
    area = cv2.contourArea(contour)
    if area < OPENCV_MIN_CONTOUR_AREA:
        return None, {}

    x, y, w, h = cv2.boundingRect(contour)
    aspect = w / h if h > 0 else 0
    cx, cy = x + w // 2, y + h // 2
    hsv = img_hsv[cy, cx]
    hue, sat, val = int(hsv[0]), int(hsv[1]), int(hsv[2])

    # Arrow: bright red, tall thin shape
    is_red_hue = hue <= OPENCV_ARROW_HUE_LOW or hue >= OPENCV_ARROW_HUE_HIGH
    is_bright = sat > OPENCV_ARROW_SAT_MIN and val > OPENCV_ARROW_VAL_MIN
    is_tall_thin = aspect < OPENCV_ARROW_ASPECT_MAX and h > OPENCV_ARROW_MIN_HEIGHT
    is_arrow_sized = OPENCV_ARROW_AREA_MIN < area < OPENCV_ARROW_AREA_MAX

    if is_red_hue and is_bright and is_tall_thin and is_arrow_sized:
        return "arrow", ArrowData(x=cx, y=cy, w=w, h=h, area=area)

    # Dot: circular shape
    is_dot_sized = OPENCV_DOT_AREA_MIN < area < OPENCV_DOT_AREA_MAX
    is_circular = OPENCV_DOT_ASPECT_MIN < aspect < OPENCV_DOT_ASPECT_MAX
    if is_dot_sized and is_circular:
        return "dot", DotData(x=cx, y=cy, area=area, hue=hue)

    return None, {}


def map_dot_to_trait(dot: DotData, x_start: int, x_end: int) -> tuple[str | None, int]:
    """Map a detected dot to its trait letter based on hue.

    Args:
        dot: DotData with hue, area, x keys.
        x_start: X coordinate for position 0.
        x_end: X coordinate for position 10.

    Returns:
        Tuple of (trait_letter, scale_value) or (None, 0) if invalid.
    """
    h, area = dot["hue"], dot["area"]
    val = pixel_to_scale(dot["x"], x_start, x_end)
    # Ensure val is int for return type
    val = int(val)

    if h >= OPENCV_HUE_A_HIGH or (h <= OPENCV_HUE_A_LOW and area > OPENCV_A_MIN_AREA):
        return "a", val
    if OPENCV_HUE_B_MIN <= h <= OPENCV_HUE_B_MAX:
        return "b", val
    if OPENCV_HUE_C_MIN <= h <= OPENCV_HUE_C_MAX:
        return "c", val
    if OPENCV_HUE_D_MIN <= h <= OPENCV_HUE_D_MAX:
        return "d", val
    if OPENCV_HUE_L_MIN <= h <= OPENCV_HUE_L_MAX:
        return "l", val
    if OPENCV_HUE_I_MIN <= h < OPENCV_HUE_C_MIN:
        return "i", val
    return None, 0


def _extract_chart(
    dots: list[DotData],
    arrows: list[ArrowData],
    eu_region: tuple[int, int, int, int],
    img_rgb: np.ndarray,
    x_start: int,
    x_end: int,
) -> dict[str, int | float | None]:
    """Extract trait values, arrow position, and EU from one chart.

    Args:
        dots: List of detected dots in this chart region.
        arrows: List of detected arrows in this chart region.
        eu_region: (x1, y1, x2, y2) for EU text area.
        img_rgb: RGB image for OCR.
        x_start: X coordinate for position 0.
        x_end: X coordinate for position 10.

    Returns:
        Dict with trait values, arrow, and EU.
    """
    result: dict[str, int | float | None] = {"a": 0, "b": 0, "c": 0, "d": 0, "l": 0, "i": 0}

    for dot in dots:
        trait, val = map_dot_to_trait(dot, x_start, x_end)
        if trait:
            result[trait] = val

    if arrows:
        sorted_arrows = sorted(arrows, key=lambda a: a["area"], reverse=True)
        result["arrow"] = pixel_to_scale(sorted_arrows[0]["x"], x_start, x_end, as_float=True)

    eu = _extract_eu(img_rgb, eu_region)
    if eu is not None:
        result["eu"] = eu

    return result


def extract_with_opencv(pdf_path: Path) -> dict[str, object]:
    """Extract chart values and metadata using OpenCV color detection and OCR.

    Supports the new landscape PDF format with charts on left and metadata on right.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Dictionary with survey_traits, job_behaviors, metadata, and _warnings list.
    """
    # Clear warnings from previous extraction
    clear_extraction_warnings()

    images = convert_from_path(str(pdf_path), dpi=300)
    img_rgb = np.array(images[0])
    img_hsv = cv2.cvtColor(cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2HSV)
    height, width = img_rgb.shape[:2]

    # Detect colored elements
    sat, val = img_hsv[:, :, 1], img_hsv[:, :, 2]
    mask = (((sat > OPENCV_SATURATION_MIN) & (val > OPENCV_VALUE_MIN)) * 255).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    header_dot_y_max = int(height * OPENCV_HEADER_DOT_Y_MAX)

    dots: list[DotData] = []
    arrows: list[ArrowData] = []
    for contour in contours:
        elem_type, data = _classify_contour(contour, img_hsv)
        if elem_type == "dot" and isinstance(data, dict) and "hue" in data:
            if data["y"] < header_dot_y_max:
                continue
            dots.append(data)  # type: ignore[arg-type]
        elif elem_type == "arrow" and isinstance(data, dict) and "w" in data:
            arrows.append(data)  # type: ignore[arg-type]

    # Chart region boundaries
    survey_y = (int(height * OPENCV_SURVEY_Y_START), int(height * OPENCV_SURVEY_Y_END))
    job_y = (int(height * OPENCV_JOB_Y_START), int(height * OPENCV_JOB_Y_END))

    # Filter by region and extract
    survey_dots = [d for d in dots if survey_y[0] < d["y"] < survey_y[1]]
    survey_arrows = [a for a in arrows if survey_y[0] < a["y"] < survey_y[1]]
    job_dots = [d for d in dots if job_y[0] < d["y"] < job_y[1]]
    job_arrows = [a for a in arrows if job_y[0] < a["y"] < job_y[1]]

    survey_eu_region = (OPENCV_EU_REGION_X_START, survey_y[0], OPENCV_EU_REGION_X_END, survey_y[1])
    job_eu_region = (OPENCV_EU_REGION_X_START, job_y[0], OPENCV_EU_REGION_X_END, job_y[1])

    survey_data = _extract_chart(
        survey_dots,
        survey_arrows,
        survey_eu_region,
        img_rgb,
        OPENCV_CHART_X_START,
        OPENCV_CHART_X_END,
    )
    job_data = _extract_chart(
        job_dots,
        job_arrows,
        job_eu_region,
        img_rgb,
        OPENCV_CHART_X_START,
        OPENCV_CHART_X_END,
    )

    header_info = _extract_header_info(img_rgb, height, width)

    # Fallback: parse name from filename if OCR failed
    if "name" not in header_info:
        filename_name = _parse_name_from_filename(pdf_path.stem)
        if _is_valid_name(filename_name):
            header_info["name"] = filename_name
        else:
            _extraction_warnings.append(
                f"Could not extract name from PDF or filename: {pdf_path.name}"
            )
            header_info["name"] = "Unknown"  # Ensure name field always exists

    # Add warnings to result if any
    result: dict[str, object] = {
        "survey_traits": survey_data,
        "job_behaviors": job_data,
        **header_info,
    }

    if _extraction_warnings:
        result["_warnings"] = get_extraction_warnings()

    return result
