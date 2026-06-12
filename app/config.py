from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"
ANALYSIS_DIR = DATA_DIR / "analysis"
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
