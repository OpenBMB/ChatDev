"""Configuration constants for Culture Index extraction.

Contains OpenCV calibration values for extracting trait data from PDF charts.
"""

# =============================================================================
# OpenCV Extraction Constants (calibrated for 300 DPI landscape Culture Index PDFs)
# =============================================================================

# Chart region boundaries as percentage of image height
# Survey Traits chart: ~26-50% of page height
# Job Behaviors chart: ~63-87% of page height
OPENCV_SURVEY_Y_START = 0.25
OPENCV_SURVEY_Y_END = 0.51
OPENCV_JOB_Y_START = 0.62
OPENCV_JOB_Y_END = 0.88

# X-axis calibration in pixels (at 300 DPI, landscape ~3300px width)
# Charts occupy left ~60% of page
# Position 0 is at x=686, position 10 is at x=1994 (130.8 px per unit)
OPENCV_CHART_X_START = 686
OPENCV_CHART_X_END = 1994

# EU text region: left of chart grid where "EU = XX" appears
OPENCV_EU_REGION_X_START = 0
OPENCV_EU_REGION_X_END = 686

# Header dots filter: decorative archetype color dots at top (not trait data)
# Header dots are at ~11% of page height
OPENCV_HEADER_DOT_Y_MAX = 0.12

# Metadata column (right side of page, avoid chart overlap)
OPENCV_METADATA_X_START = 0.65  # 65% of page width (further right to avoid chart)
OPENCV_METADATA_Y_START = 0.08
OPENCV_METADATA_Y_END = 0.55

# Header regions (top-left area)
OPENCV_NAME_REGION_Y_END = 0.06
OPENCV_COMPANY_REGION_Y_END = 0.10
OPENCV_ARCHETYPE_REGION_Y_END = 0.18

# HSV color detection thresholds
# Saturation and value must exceed these to be considered a colored element
OPENCV_SATURATION_MIN = 80
OPENCV_VALUE_MIN = 80

# Arrow detection: bright red with high saturation/value
# Distinguishes red arrow from dark maroon A-trait dot
OPENCV_ARROW_SAT_MIN = 150
OPENCV_ARROW_VAL_MIN = 150
OPENCV_ARROW_HUE_LOW = 8  # Red wraps around 0/180
OPENCV_ARROW_HUE_HIGH = 175

# Element area thresholds in pixels
OPENCV_MIN_CONTOUR_AREA = 100  # Ignore tiny noise
OPENCV_DOT_AREA_MIN = 500  # Trait dots are larger
OPENCV_DOT_AREA_MAX = 8000
OPENCV_ARROW_AREA_MIN = 200
OPENCV_ARROW_AREA_MAX = 5000

# Arrow shape: must be tall and thin (width/height < 0.3, height > 50px)
OPENCV_ARROW_ASPECT_MAX = 0.3
OPENCV_ARROW_MIN_HEIGHT = 50

# Dot shape: roughly circular (aspect ratio between 0.3 and 3.0)
OPENCV_DOT_ASPECT_MIN = 0.3
OPENCV_DOT_ASPECT_MAX = 3.0

# Hue ranges for trait colors (OpenCV uses 0-180 for hue)
# A (maroon/dark red): hue >= 165 or hue <= 5 with large area
OPENCV_HUE_A_HIGH = 165
OPENCV_HUE_A_LOW = 5
OPENCV_A_MIN_AREA = 1500  # A dots are larger than noise

# B (yellow): hue 15-35
OPENCV_HUE_B_MIN = 15
OPENCV_HUE_B_MAX = 35

# C (blue): hue 105-115
OPENCV_HUE_C_MIN = 105
OPENCV_HUE_C_MAX = 115

# D (green): hue 65-85
OPENCV_HUE_D_MIN = 65
OPENCV_HUE_D_MAX = 85

# L (purple/magenta): hue 135-165
OPENCV_HUE_L_MIN = 135
OPENCV_HUE_L_MAX = 165

# I (cyan): hue 85 to C_MIN (uses C_MIN as upper bound to avoid overlap)
OPENCV_HUE_I_MIN = 85

# =============================================================================
# Culture Index Archetypes (known valid values from profiles)
# =============================================================================

# Archetypes observed in actual Culture Index PDFs
# Used by opencv_extractor.py for OCR matching
ARCHETYPES = [
    # From actual profiles
    "Administrator",
    "Architect",
    "Chameleon",
    "Coordinator",
    "Craftsman",
    "Debater",
    "Enterpriser",
    "Facilitator",
    "Influencer",
    "Philosopher",
    "Rainmaker",
    "Scholar",
    "Socializer",
    "Specialist",
    "Technical Expert",
    "Traditionalist",
    # From methodology documentation
    "Accommodator",
    "Persuader",
    "Visionary",
]
