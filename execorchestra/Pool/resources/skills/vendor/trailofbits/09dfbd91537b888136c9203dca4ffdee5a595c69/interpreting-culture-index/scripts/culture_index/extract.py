"""Extract Culture Index profiles from PDFs to JSON format.

This module provides functions for extracting profile data from Culture Index
PDF files using OpenCV (100% accuracy) and generating JSON output with
methodology-aligned interpretations.

Output includes:
- Distance from arrow for primary traits (A, B, C, D)
- Separate handling for L/I (absolute scale, not relative to arrow)
- Energy utilization analysis with health indicators
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from culture_index.models import ExtractionResult
from culture_index.opencv_extractor import extract_with_opencv, get_extraction_warnings


def calculate_energy_utilization(survey_eu: int, job_eu: int) -> tuple[int, str]:
    """Calculate energy utilization percentage and health indicator.

    Formula: (Job EU / Survey EU) x 100

    - 70-130%: Healthy (sustainable workload alignment)
    - >130%: Stress (burnout risk, overutilization)
    - <70%: Frustration (disengaged, flight risk)

    Args:
        survey_eu: Energy Units from Survey Traits graph.
        job_eu: Energy Units from Job Behaviors graph.

    Returns:
        Tuple of (percentage, status) where status is one of:
        'healthy', 'stress', 'frustration', 'invalid'.
    """
    if survey_eu == 0:
        return 0, "invalid"
    util = round((job_eu / survey_eu) * 100)
    if util < 70:
        return util, "frustration"
    if util > 130:
        return util, "stress"
    return util, "healthy"


def _build_chart_data(chart: dict) -> dict:
    """Build chart data with array format [absolute, relative].

    All traits use [score, distance_from_arrow] format.
    Logic/Ingenuity have null for relative (absolute values per methodology).

    Args:
        chart: Raw chart data with a, b, c, d, l, i, eu, arrow.

    Returns:
        Chart data with traits as [absolute, relative] arrays.
    """
    arrow = chart.get("arrow", 0)

    result = {
        "eu": chart.get("eu"),
        "arrow": arrow,
    }

    # Primary traits: A, B, C, D - [score, distance_from_arrow]
    for trait in ["a", "b", "c", "d"]:
        score = chart.get(trait, 0)
        result[trait] = [score, round(score - arrow, 1)]

    # Secondary traits: L, I - [score, null] (absolute values per methodology)
    result["logic"] = [chart.get("l", 0), None]
    result["ingenuity"] = [chart.get("i", 0), None]

    return result


def generate_json(data: dict) -> dict:
    """Generate JSON output from extracted profile data.

    Args:
        data: Dictionary containing raw extracted profile fields.

    Returns:
        JSON-serializable dictionary with flat structure.
    """
    survey = data.get("survey_traits", {})
    job = data.get("job_behaviors", {})

    # Calculate energy utilization
    survey_eu = survey.get("eu", 0) or 0
    job_eu = job.get("eu", 0) or 0
    eu_percent, eu_status = calculate_energy_utilization(survey_eu, job_eu)

    return {
        "name": data.get("name"),
        "archetype": data.get("archetype"),
        "header": {
            "job_title": data.get("job_title"),
            "location": data.get("location"),
            "email": data.get("email"),
            "date": data.get("date"),
            "administered_by": data.get("administered_by"),
            "survey_type": data.get("survey_type"),
            "survey_id": data.get("survey_id"),
        },
        "survey": _build_chart_data(survey),
        "job": _build_chart_data(job),
        "analysis": {
            "energy_utilization": eu_percent,
            "status": eu_status,
        },
    }


def process_pdf(pdf_path: Path, output_path: Path | None = None) -> ExtractionResult:
    """Process a single PDF file and generate JSON output.

    Uses OpenCV for extraction (100% accuracy, no API keys needed).

    Args:
        pdf_path: Path to the PDF file.
        output_path: Optional path for output JSON file.
                    If None, outputs to stdout.

    Returns:
        ExtractionResult with success status and output path.
    """
    pdf_path = Path(pdf_path)

    # Validate input
    if not pdf_path.exists():
        return ExtractionResult(
            pdf_name=pdf_path.name,
            success=False,
            error=f"PDF not found: {pdf_path}",
        )
    if not pdf_path.is_file():
        return ExtractionResult(
            pdf_name=pdf_path.name,
            success=False,
            error=f"Not a file: {pdf_path}",
        )

    try:
        # Extract with OpenCV
        extracted_data = extract_with_opencv(pdf_path)

        # Capture any warnings from extraction
        warnings = get_extraction_warnings()

        # Generate JSON output
        output_data = generate_json(extracted_data)

        # Write to file or stdout
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(output_data, indent=2))
            return ExtractionResult(
                pdf_name=pdf_path.name,
                success=True,
                output_path=str(output_path),
                warnings=warnings,
            )
        else:
            # Print to stdout
            print(json.dumps(output_data, indent=2))
            return ExtractionResult(
                pdf_name=pdf_path.name,
                success=True,
                warnings=warnings,
            )

    except Exception as e:
        # Log full traceback to stderr for debugging
        print(f"Extraction failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return ExtractionResult(
            pdf_name=pdf_path.name,
            success=False,
            error=str(e),
        )
