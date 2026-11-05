#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "opencv-python-headless>=4.10.0,<5.0",
#     "numpy>=2.0.0,<3.0",
#     "pdf2image>=1.17.0,<2.0",
#     "pytesseract>=0.3.10,<1.0",
# ]
# ///
"""Extract Culture Index profile data from PDF to JSON.

Simple wrapper script for Claude to run when extracting data from Culture Index PDFs.
Uses OpenCV-based extraction (100% accuracy, no API keys needed).

Usage:
    uv run extract_pdf.py <input.pdf> [output.json]
    uv run extract_pdf.py --verify <input.pdf>

Examples:
    # Extract and print to stdout
    uv run extract_pdf.py profile.pdf

    # Extract with verification summary (recommended)
    uv run extract_pdf.py --verify profile.pdf

    # Extract and save to file
    uv run extract_pdf.py profile.pdf profile.json

Output Format:
    {
      "name": "Person Name",
      "archetype": "Architect",
      "survey": {
        "eu": 21,
        "arrow": 2.3,
        "a": [5, 2.7],      // [absolute, relative_to_arrow]
        "b": [0, -2.3],
        "c": [1, -1.3],
        "d": [3, 0.7],
        "logic": [5, null],
        "ingenuity": [2, null]
      },
      "job": { ... },
      "analysis": {
        "energy_utilization": 148,
        "status": "stress"
      }
    }

System Requirements:
    macOS:
        brew install poppler tesseract

    Ubuntu/Debian:
        apt-get install poppler-utils tesseract-ocr
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

# Add scripts directory to path for culture_index import
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from culture_index.extract import process_pdf  # noqa: E402


def render_chart(chart: dict, title: str) -> list[str]:
    """Render a chart as ASCII art matching PDF layout.

    Args:
        chart: Chart data with traits as [absolute, relative] arrays.
        title: Chart title (e.g., "Survey Traits")

    Returns:
        List of lines to print.
    """
    lines = []
    eu = chart.get("eu", "?")
    arrow = chart.get("arrow", 0)

    lines.append(f"{title} (EU={eu})")
    lines.append("        0   1   2   3   4   5   6   7   8   9  10")

    # Primary traits
    for trait in ["a", "b", "c", "d"]:
        values = chart.get(trait, [0, 0])
        score = int(values[0]) if values else 0
        # Build the line with dot at correct position
        line = f"    {trait.upper()}   "
        for i in range(11):
            if i == score:
                line += "●   "
            else:
                line += "    "
        line += f"[{score}]"
        lines.append(line)

    # Secondary traits (L, I)
    for trait, key in [("L", "logic"), ("I", "ingenuity")]:
        values = chart.get(key, [0, None])
        score = int(values[0]) if values else 0
        line = f"    {trait}   "
        for i in range(11):
            if i == score:
                line += "●   "
            else:
                line += "    "
        line += f"[{score}]"
        lines.append(line)

    # Arrow indicator
    arrow_pos = int(round(arrow))
    arrow_line = "        "
    for i in range(11):
        if i == arrow_pos:
            arrow_line += "↑   "
        else:
            arrow_line += "    "
    arrow_line += f"arrow ({arrow})"
    lines.append(arrow_line)

    return lines


def print_verification_summary(data: dict) -> None:
    """Print a verification summary with ASCII charts to stderr.

    Args:
        data: Extracted JSON data.
    """
    print("\n" + "=" * 60, file=sys.stderr)
    print("VERIFICATION SUMMARY - Compare with PDF", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Name: {data.get('name', 'Unknown')}", file=sys.stderr)
    print(f"Pattern: {data.get('archetype', 'Unknown')}", file=sys.stderr)
    print(file=sys.stderr)

    # Survey chart
    survey = data.get("survey", {})
    for line in render_chart(survey, "Survey Traits"):
        print(line, file=sys.stderr)
    print(file=sys.stderr)

    # Job chart
    job = data.get("job", {})
    for line in render_chart(job, "Job Behaviors"):
        print(line, file=sys.stderr)
    print(file=sys.stderr)

    # Energy utilization
    analysis = data.get("analysis", {})
    eu_pct = analysis.get("energy_utilization", 0)
    eu_status = analysis.get("status", "unknown")
    status_indicator = {
        "healthy": "✓",
        "stress": "⚠️ STRESS",
        "frustration": "⚠️ FRUSTRATION",
    }.get(eu_status, "?")
    print(f"Energy Utilization: {eu_pct}% ({status_indicator})", file=sys.stderr)
    print("=" * 60 + "\n", file=sys.stderr)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract Culture Index profile data from PDF to JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run extract_pdf.py profile.pdf              # Print JSON to stdout
  uv run extract_pdf.py --verify profile.pdf     # Print JSON + verification summary
  uv run extract_pdf.py profile.pdf out.json     # Save to file
        """,
    )
    parser.add_argument("pdf", type=Path, help="Input PDF file path")
    parser.add_argument("output", type=Path, nargs="?", help="Output JSON file path (optional)")
    parser.add_argument(
        "--verify",
        "-v",
        action="store_true",
        help="Show verification summary for spot-checking (recommended)",
    )

    args = parser.parse_args()

    # Capture stdout if we need to parse the JSON for verification
    if args.verify and not args.output:
        # Capture the JSON output
        captured = io.StringIO()
        with redirect_stdout(captured):
            result = process_pdf(args.pdf, args.output)

        if result.success:
            json_output = captured.getvalue()
            print(json_output)  # Print JSON to stdout

            # Parse and show verification
            try:
                data = json.loads(json_output)
                print_verification_summary(data)
            except json.JSONDecodeError:
                print("Warning: Could not parse JSON for verification", file=sys.stderr)
            return 0
        else:
            print(f"Error: {result.error}", file=sys.stderr)
            return 1
    else:
        # Normal operation
        result = process_pdf(args.pdf, args.output)

        if result.success:
            if args.output:
                print(f"Extracted: {result.output_path}", file=sys.stderr)

                # If --verify and output file, read and verify
                if args.verify:
                    try:
                        data = json.loads(args.output.read_text())
                        print_verification_summary(data)
                    except (json.JSONDecodeError, FileNotFoundError):
                        print("Warning: Could not read output for verification", file=sys.stderr)
            return 0
        else:
            print(f"Error: {result.error}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    sys.exit(main())
