import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"
ANALYSIS_DIR = DATA_DIR / "analysis"
ANALYSIS_RESULT_FILE = ANALYSIS_DIR / "last_centroid_analysis.json"
GENERATED_STATIC_DIR = STATIC_DIR / "generated" / "analysis"
DATA_FILE = DATA_DIR / "color_sensor_samples.csv"
CSV_HEADER = ("color_name", *[f"channel{index}" for index in range(1, 11)])
CAPTURE_TARGET_SAMPLES = 100
ARDUINO_RESET_COMMAND = ("arduino-reset",)
BRIDGE_SAMPLE_METHOD = "color_sensor.sample"
BRIDGE_START_METHOD = "color_sensor.capture.start"
BRIDGE_STOP_METHOD = "color_sensor.capture.stop"
BRIDGE_SENSOR_READY_METHOD = "color_sensor.sensor.ready"

CAPTURE_COLORS = (
    "red",
    "purple",
    "green",
    "yellow",
    "orange",
    "blue",
    "pink",
)


COLOR_BADGES = {
    "red": "text-bg-danger",
    "purple": "text-bg-primary",
    "green": "text-bg-success",
    "yellow": "text-bg-warning",
    "orange": "text-bg-warning",
    "blue": "text-bg-info",
    "pink": "text-bg-secondary",
}


def _normalize_route_path(raw_path: str) -> str:
    normalized = raw_path.strip()
    if not normalized:
        normalized = "la-face-cachee-de-la-lune"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    if len(normalized) > 1:
        normalized = normalized.rstrip("/")
    return normalized or "/la-face-cachee-de-la-lune"


DOOM_PAGE_PATH = _normalize_route_path(
    os.getenv("M2614_DOOM_PATH", "la-face-cachee-de-la-lune")
)
DOOM_PAGE_TITLE = "The Hidden Side of the Moon"
DOOM_BUNDLE_STATIC_PATH = "vendor/doom/doom-shareware.jsdos"
