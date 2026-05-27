from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from typing import cast

import psutil

from .config import (
    BALL_STYLES,
    CALIBRATION_OPTIONS,
    ROBOT_MODES,
    CalibrationOption,
    RobotMode,
)


class PlaceholderStore:
    """Hold the shared in-memory placeholder state for the dashboard.

    The store centralizes the fake monitoring data and interactive control state
    used by the current Bootstrap dashboard until real hardware telemetry and
    commands are wired in through the bridge layer.
    """

    def __init__(self) -> None:
        """Initialize the placeholder dashboard state.

        The initial state mirrors a robot in standby, primes the CPU usage probe
        so subsequent readings are meaningful, and records the first activity log
        entry displayed by the frontend.
        """
        self._lock = RLock()
        self.mode = "standby"
        self.sorting_forced = False
        self.ball_count = 18
        self.current_ball_color = "Blue"
        self.current_ball_confidence = 91
        self.lidar_scan_id = 0
        self.lidar_frequency_hz = 0.0
        self.last_action = "Dashboard template initialized."
        self.last_calibration = "None"
        self.updated_at = self._timestamp_label()
        self.events: list[dict[str, str]] = []

        psutil.cpu_percent(interval=None)
        self._log_event(self.last_action, "text-bg-secondary")

    def dashboard_payload(self) -> dict[str, object]:
        """Assemble the complete placeholder payload used by the dashboard UI.

        Returns:
            dict[str, object]: A structured snapshot containing system metrics,
            sorter information, robot state, LiDAR placeholder data, available
            modes, calibration actions, activity events, and metadata.
        """
        with self._lock:
            current_mode = self._mode_by_key(self.mode)
            current_ball = self._current_ball_payload()
            robot = self._robot_payload(current_mode)
            payload: dict[str, object] = {
                "system": self.system_metrics(),
                "sorter": {
                    "ball_count": self.ball_count,
                    "enabled": self.sorting_forced or self.mode in {"sorting", "unloading"},
                    "current_ball": current_ball,
                    "status_note": "Placeholder classifier output ready for Bridge-backed telemetry later.",
                },
                "robot": robot,
                "lidar": {
                    "placeholder": True,
                    "scan_id": self.lidar_scan_id,
                    "frequency_hz": self.lidar_frequency_hz,
                    "point_count": 0,
                    "message": "Canvas reserved for the future 2D LiDAR live map.",
                },
                "modes": [self._mode_view(mode) for mode in ROBOT_MODES],
                "calibrations": [self._calibration_view(option) for option in CALIBRATION_OPTIONS],
                "events": list(self.events),
                "meta": {
                    "last_action": self.last_action,
                    "last_calibration": self.last_calibration,
                    "updated_at": self.updated_at,
                },
            }
            return payload

    def system_metrics(self) -> dict[str, float]:
        """Read the current host CPU and RAM usage.

        Returns:
            dict[str, float]: CPU and memory usage percentages for the machine
            running the dashboard service.
        """
        return {
            "cpu_percent": round(psutil.cpu_percent(interval=None), 1),
            "ram_percent": round(psutil.virtual_memory().percent, 1),
        }

    def lidar_status(self) -> dict[str, object]:
        """Return the LiDAR-specific subset of the dashboard payload.

        Returns:
            dict[str, object]: The placeholder LiDAR panel data consumed by the
            monitoring page and the dedicated API endpoint.
        """
        payload = self.dashboard_payload()
        return cast(dict[str, object], payload["lidar"])

    def modes_payload(self) -> list[dict[str, object]]:
        """Return the available robot modes with their active flag.

        Returns:
            list[dict[str, object]]: All configured modes in a frontend-friendly
            structure suitable for rendering selectors and API payloads.
        """
        with self._lock:
            return [self._mode_view(mode) for mode in ROBOT_MODES]

    def set_mode(self, mode_key: str) -> dict[str, object]:
        """Switch the placeholder robot state machine to a new mode.

        Args:
            mode_key: Key of the target robot mode.

        Returns:
            dict[str, object]: The refreshed dashboard payload after the mode
            change has been applied.

        Raises:
            ValueError: Raised when ``mode_key`` does not match any configured
            robot mode.
        """
        with self._lock:
            selected_mode = self._mode_by_key(mode_key)
            self.mode = selected_mode.key
            if selected_mode.key == "emergency":
                self.sorting_forced = False
            self.last_action = f"Robot mode switched to {selected_mode.label}."
            self.updated_at = self._timestamp_label()
            self._log_event(
                self.last_action,
                "text-bg-danger" if selected_mode.key == "emergency" else "text-bg-primary",
            )
            return self.dashboard_payload()

    def set_sorting_enabled(self, enabled: bool) -> dict[str, object]:
        """Enable or disable the manual sorting override.

        Args:
            enabled: ``True`` to force-enable the sorting system, ``False`` to
            release the manual override.

        Returns:
            dict[str, object]: The refreshed dashboard payload after the sorting
            override state changes.

        Raises:
            ValueError: Raised when forced sorting is requested while the robot is
            in emergency mode.
        """
        with self._lock:
            if self.mode == "emergency" and enabled:
                raise ValueError(
                    "Forced sorting is blocked while emergency mode is active.")

            self.sorting_forced = enabled
            self.last_action = (
                "Manual sorting override enabled."
                if enabled
                else "Manual sorting override disabled."
            )
            self.updated_at = self._timestamp_label()
            self._log_event(
                self.last_action,
                "text-bg-success" if enabled else "text-bg-secondary",
            )
            return self.dashboard_payload()

    def run_calibration(self, calibration_key: str) -> dict[str, object]:
        """Queue a placeholder calibration sequence.

        Args:
            calibration_key: Key identifying which calibration routine should be
            marked as queued.

        Returns:
            dict[str, object]: The refreshed dashboard payload after the
            calibration event has been recorded.

        Raises:
            ValueError: Raised when ``calibration_key`` does not match any known
            calibration option.
        """
        with self._lock:
            calibration = self._calibration_by_key(calibration_key)
            self.last_calibration = calibration.label
            self.last_action = f"{calibration.label} calibration queued in placeholder mode."
            self.updated_at = self._timestamp_label()
            self._log_event(self.last_action, "text-bg-warning")
            return self.dashboard_payload()

    def _current_ball_payload(self) -> dict[str, object]:
        style = BALL_STYLES.get(self.current_ball_color,
                                BALL_STYLES["Unknown"])
        return {
            "label": self.current_ball_color,
            "confidence": self.current_ball_confidence,
            "badge_class": style["badge_class"],
            "progress_class": style["progress_class"],
        }

    def _robot_payload(self, current_mode: RobotMode) -> dict[str, object]:
        flags = [
            self._flag_view(
                key="autonomous",
                label="Autonomous",
                active=self.mode in {"autonomous", "sorting", "unloading"},
                active_label="Engaged",
                inactive_label="Idle",
                active_class="text-bg-success",
                inactive_class="text-bg-secondary",
            ),
            self._flag_view(
                key="waiting",
                label="Waiting",
                active=self.mode == "standby",
                active_label="Awaiting command",
                inactive_label="Executing",
                active_class="text-bg-warning",
                inactive_class="text-bg-success",
            ),
            self._flag_view(
                key="emergency",
                label="Emergency stop",
                active=self.mode == "emergency",
                active_label="Triggered",
                inactive_label="Clear",
                active_class="text-bg-danger",
                inactive_class="text-bg-success",
            ),
            self._flag_view(
                key="sorting-system",
                label="Sorting system",
                active=self.sorting_forced or self.mode in {
                    "sorting", "unloading"},
                active_label="Armed",
                inactive_label="Standby",
                active_class="text-bg-info",
                inactive_class="text-bg-secondary",
            ),
            self._flag_view(
                key="rc-link",
                label="RC receiver",
                active=self.mode == "remote-control",
                active_label="Operator linked",
                inactive_label="Passive",
                active_class="text-bg-primary",
                inactive_class="text-bg-secondary",
            ),
        ]

        return {
            "current_mode": {
                "key": current_mode.key,
                "label": current_mode.label,
                "badge_class": current_mode.badge_class,
            },
            "status_note": current_mode.status_note,
            "flags": flags,
            "sorting_forced": self.sorting_forced,
            "summary": "Placeholder robot state machine surface ready for real modes later.",
        }

    def _flag_view(
        self,
        *,
        key: str,
        label: str,
        active: bool,
        active_label: str,
        inactive_label: str,
        active_class: str,
        inactive_class: str,
    ) -> dict[str, str]:
        return {
            "key": key,
            "label": label,
            "state_label": active_label if active else inactive_label,
            "badge_class": active_class if active else inactive_class,
        }

    def _mode_view(self, mode: RobotMode) -> dict[str, object]:
        return {
            "key": mode.key,
            "label": mode.label,
            "description": mode.description,
            "badge_class": mode.badge_class,
            "is_active": mode.key == self.mode,
        }

    def _calibration_view(self, calibration: CalibrationOption) -> dict[str, str]:
        return {
            "key": calibration.key,
            "label": calibration.label,
            "description": calibration.description,
        }

    def _mode_by_key(self, mode_key: str) -> RobotMode:
        for mode in ROBOT_MODES:
            if mode.key == mode_key:
                return mode
        raise ValueError(f"Unknown robot mode: {mode_key}")

    def _calibration_by_key(self, calibration_key: str) -> CalibrationOption:
        for calibration in CALIBRATION_OPTIONS:
            if calibration.key == calibration_key:
                return calibration
        raise ValueError(f"Unknown calibration sequence: {calibration_key}")

    def _log_event(self, message: str, badge_class: str) -> None:
        self.events.insert(
            0,
            {
                "timestamp": self._timestamp_label(),
                "message": message,
                "badge_class": badge_class,
            },
        )
        del self.events[6:]

    def _timestamp_label(self) -> str:
        return datetime.now(UTC).strftime("%H:%M:%S UTC")
