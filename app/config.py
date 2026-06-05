from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"
DATA_FILE = DATA_DIR / "color_sensor_samples.csv"
CAPTURE_TARGET_SAMPLES = 100
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
