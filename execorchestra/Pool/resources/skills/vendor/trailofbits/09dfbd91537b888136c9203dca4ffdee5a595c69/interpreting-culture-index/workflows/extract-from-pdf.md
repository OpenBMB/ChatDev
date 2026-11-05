# Extract from PDF Workflow

Extract Culture Index profile data from a PDF file and convert to JSON format.

## Prerequisites

**Required:**
- `uv` - Install with `brew install uv` or `pip install uv`
- `poppler` - Install with `brew install poppler` (macOS) or `apt install poppler-utils` (Ubuntu)
- `tesseract` - Install with `brew install tesseract` (macOS) or `apt install tesseract-ocr` (Ubuntu)

## Extraction Command

Single command, no setup required:

```bash
uv run {baseDir}/scripts/extract_pdf.py --verify /path/to/profile.pdf
```

**Options:**
- `--verify`, `-v` - Show verification summary for spot-checking (recommended)
- Second argument - Output path for JSON (optional, defaults to stdout)

**Examples:**
```bash
# Extract with verification (recommended)
uv run {baseDir}/scripts/extract_pdf.py --verify profile.pdf

# Extract and save to file
uv run {baseDir}/scripts/extract_pdf.py profile.pdf output.json

# Extract and pipe to jq
uv run {baseDir}/scripts/extract_pdf.py profile.pdf | jq '.survey'
```

## What Happens

1. `uv` creates a temporary environment with all Python dependencies (PEP 723)
2. Script extracts trait values using OpenCV (100% accuracy)
3. With `--verify`, displays summary table for manual confirmation
4. Outputs JSON to stdout or specified file

## Verification Summary

When using `--verify`, you'll see ASCII charts that match the PDF layout:

```
============================================================
VERIFICATION SUMMARY - Compare with PDF
============================================================
Name: Sara Davis
Pattern: Specialist

Survey Traits (EU=18)
        0   1   2   3   4   5   6   7   8   9  10
    A       ●                                       [1]
    B       ●                                       [1]
    C       ●                                       [1]
    D           ●                                   [2]
    L                                   ●           [8]
    I       ●                                       [1]
            ↑                                       arrow (1.3)

Job Behaviors (EU=26)
        0   1   2   3   4   5   6   7   8   9  10
    A       ●                                       [1]
    B           ●                                   [2]
    C                   ●                           [4]
    D                       ●                       [5]
    L               ●                               [3]
    I                   ●                           [4]
                    ↑                               arrow (3.0)

Energy Utilization: 144% (⚠️ STRESS)
============================================================
```

**Spot-check against the PDF:**
- Each trait row: Is the ● in roughly the same position as the dot on the PDF?
- Arrow position: Does ↑ align with the red arrow on each chart?
- EU values: Match what's displayed on the PDF?

## If Extraction Fails

- **"uv not found"** → Install uv: `brew install uv`
- **"poppler not found"** → Install poppler: `brew install poppler`
- **"tesseract not found"** → Install tesseract: `brew install tesseract`

**Do NOT fall back to visual estimation.** Fix the dependency issue instead. Visual estimation has 20-30% error rate.

## Output Format

```json
{
  "name": "Person Name",
  "archetype": "Architect",
  "header": { ... },
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
```

## After Extraction

Proceed to the appropriate workflow:
- Individual interpretation: `workflows/interpret-individual.md`
- Burnout detection: `workflows/detect-burnout.md`
- Team analysis: `workflows/analyze-team.md`
