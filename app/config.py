from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


@dataclass(frozen=True, slots=True)
class RobotMode:
    key: str
    label: str
    description: str
    badge_class: str
    status_note: str


@dataclass(frozen=True, slots=True)
class CalibrationOption:
    key: str
    label: str
    description: str


ROBOT_MODES = (
    RobotMode(
        key="standby",
        label="Standby",
        description="Safe idle state while the robot waits for the next command.",
        badge_class="text-bg-secondary",
        status_note="Robot is parked and waiting for the operator or mission planner.",
    ),
    RobotMode(
        key="remote-control",
        label="Remote control",
        description="Manual operator control through the RC receiver.",
        badge_class="text-bg-primary",
        status_note="Operator inputs own motion while placeholder telemetry remains passive.",
    ),
    RobotMode(
        key="autonomous",
        label="Autonomous",
        description="Robot runs its autonomous mission without manual driving.",
        badge_class="text-bg-success",
        status_note="Autonomous mission logic is expected to own trajectory and actions.",
    ),
    RobotMode(
        key="sorting",
        label="Sorting",
        description="Sorting subsystem is prioritized while samples are classified.",
        badge_class="text-bg-warning",
        status_note="Sorting lane is the focus and ball classification should remain active.",
    ),
    RobotMode(
        key="unloading",
        label="Unloading",
        description="Payload unloading sequence is active.",
        badge_class="text-bg-info",
        status_note="Robot is assumed to be positioning and unloading sorted samples.",
    ),
    RobotMode(
        key="emergency",
        label="Emergency",
        description="Hard safety state that should stop risky behavior immediately.",
        badge_class="text-bg-danger",
        status_note="Emergency state is active. Motion and forced sorting should be considered blocked.",
    ),
)


CALIBRATION_OPTIONS = (
    CalibrationOption(
        key="motors",
        label="Motors",
        description="Placeholder launch for drive, encoder, and motion alignment checks.",
    ),
    CalibrationOption(
        key="lidar",
        label="LiDAR",
        description="Placeholder launch for the future LiDAR alignment and scan validation routine.",
    ),
    CalibrationOption(
        key="color-sensor",
        label="Color sensor",
        description="Placeholder launch for the sample color calibration workflow.",
    ),
    CalibrationOption(
        key="rc-receiver",
        label="RC receiver",
        description="Placeholder launch for RC channel centering and range checks.",
    ),
)


BALL_STYLES = {
    "Blue": {
        "badge_class": "bg-primary-subtle text-primary-emphasis border border-primary-subtle",
        "progress_class": "bg-primary",
    },
    "Yellow": {
        "badge_class": "bg-warning-subtle text-warning-emphasis border border-warning-subtle",
        "progress_class": "bg-warning",
    },
    "Green": {
        "badge_class": "bg-success-subtle text-success-emphasis border border-success-subtle",
        "progress_class": "bg-success",
    },
    "Red": {
        "badge_class": "bg-danger-subtle text-danger-emphasis border border-danger-subtle",
        "progress_class": "bg-danger",
    },
    "Unknown": {
        "badge_class": "bg-secondary-subtle text-secondary-emphasis border border-secondary-subtle",
        "progress_class": "bg-secondary",
    },
}
