from __future__ import annotations

import csv
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock, Thread

from bridge import Bridge
from logger import Logger

from .centroid_analysis import run_centroid_analysis

from .config import (
    ANALYSIS_DIR,
    ARDUINO_RESET_COMMAND,
    BRIDGE_SAMPLE_METHOD,
    BRIDGE_SENSOR_READY_METHOD,
    BRIDGE_START_METHOD,
    BRIDGE_STOP_METHOD,
    CAPTURE_COLORS,
    CAPTURE_TARGET_SAMPLES,
    CSV_HEADER,
    COLOR_BADGES,
    DATA_DIR,
    DATA_FILE,
    GENERATED_STATIC_DIR,
)


logger = Logger("CaptureStore")


class CaptureStore:
    """Hold the shared state for the color-sensor calibration capture app."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._csv_lock = RLock()
        self._data_file = DATA_FILE
        self._capture_active = False
        self._selected_color: str | None = None
        self._sample_count = 0
        self._target_samples = CAPTURE_TARGET_SAMPLES
        self._last_sample: list[int] = []
        self._status_message = "Waiting for the bridge registration to complete."
        self._updated_at = self._timestamp_label()
        self._bridge_connected = False
        self._bridge_last_error: str | None = None
        self._sensor_ready = False
        self._analysis_message = "No centroid analysis has been run yet."
        self._analysis_error: str | None = None
        self._analysis_cpp_code = ""
        self._analysis_plot_links: list[dict[str, str]] = []
        self._analysis_unknown_threshold: float | None = None
        self._analysis_silhouette_score: float | None = None
        self._analysis_sample_count = 0
        self._analysis_class_sizes: dict[str, int] = {}

        bridge_thread = Thread(
            target=self._register_bridge_handler,
            name="BridgeRegister",
            daemon=True,
        )
        bridge_thread.start()

    def status_payload(self) -> dict[str, object]:
        with self._lock:
            current_color = self._selected_color
            payload: dict[str, object] = {
                "available_colors": list(CAPTURE_COLORS),
                "selected_color": current_color,
                "selected_color_badge": self._badge_for_color(current_color),
                "capture_active": self._capture_active,
                "sample_count": self._sample_count,
                "target_samples": self._target_samples,
                "last_sample": list(self._last_sample),
                "csv_path": str(self._data_file),
                "status_message": self._status_message,
                "bridge_connected": self._bridge_connected,
                "bridge_error": self._bridge_last_error,
                "sensor_ready": self._sensor_ready,
                "analysis_message": self._analysis_message,
                "analysis_error": self._analysis_error,
                "analysis_cpp_code": self._analysis_cpp_code,
                "analysis_plot_links": list(self._analysis_plot_links),
                "analysis_unknown_threshold": self._analysis_unknown_threshold,
                "analysis_silhouette_score": self._analysis_silhouette_score,
                "analysis_sample_count": self._analysis_sample_count,
                "analysis_class_sizes": dict(self._analysis_class_sizes),
                "updated_at": self._updated_at,
            }
            return payload

    def poll_status(self) -> dict[str, object]:
        self._refresh_sensor_ready()
        return self.status_payload()

    def health_payload(self) -> dict[str, object]:
        status = self.status_payload()
        return {
            "status": "ok",
            "bridge_connected": status["bridge_connected"],
            "capture_active": status["capture_active"],
            "sensor_ready": status["sensor_ready"],
        }

    def start_gathering(self, color_name: str) -> dict[str, object]:
        normalized_color = color_name.strip().lower()
        if normalized_color not in CAPTURE_COLORS:
            raise ValueError(f"Unsupported color '{color_name}'.")

        with self._lock:
            if self._capture_active:
                raise ValueError("A gathering session is already running.")
            if not self._bridge_connected:
                raise ValueError(
                    "Bridge is not connected to the Uno Q router yet.")

        self._ensure_csv_header()
        self._refresh_sensor_ready()

        if not self._sensor_ready:
            raise ValueError("The color sensor is not ready on the Uno Q.")

        self._call_bridge(BRIDGE_START_METHOD)

        with self._lock:
            self._selected_color = normalized_color
            self._capture_active = True
            self._sample_count = 0
            self._last_sample = []
            self._clear_analysis_results_locked()
            self._status_message = f"Gathering {normalized_color} samples (0/{self._target_samples})."
            self._updated_at = self._timestamp_label()
            return self.status_payload()

    def stop_gathering(self) -> dict[str, object]:
        with self._lock:
            was_active = self._capture_active
            if not was_active:
                raise ValueError("No gathering session is currently active.")

        self._call_bridge(BRIDGE_STOP_METHOD)

        with self._lock:
            self._capture_active = False
            self._status_message = "Gathering stopped by the operator."
            self._updated_at = self._timestamp_label()
            return self.status_payload()

    def handle_color_sample(self, *channels: int) -> None:
        if len(channels) != 10:
            self._set_bridge_error(
                f"Received {len(channels)} channels, expected 10 from {BRIDGE_SAMPLE_METHOD}."
            )
            return

        try:
            sample = [int(channel) for channel in channels]
        except (TypeError, ValueError) as error:
            self._set_bridge_error(f"Invalid sample payload: {error}")
            return

        with self._lock:
            if not self._capture_active or self._selected_color is None:
                return

            color_name = self._selected_color

        self._append_csv_row(color_name, sample)

        should_stop = False
        with self._lock:
            if not self._capture_active or self._selected_color != color_name:
                return

            self._sample_count += 1
            self._last_sample = sample
            self._status_message = (
                f"Gathering {color_name} samples ({self._sample_count}/{self._target_samples})."
            )
            self._updated_at = self._timestamp_label()
            should_stop = self._sample_count >= self._target_samples
            if should_stop:
                self._capture_active = False
                self._status_message = (
                    f"Captured {self._target_samples} {color_name} samples. Stopping MCU capture."
                )

        if should_stop:
            stop_thread = Thread(
                target=self._finish_capture_after_target,
                name="BridgeStopCapture",
                daemon=True,
            )
            stop_thread.start()

    def reset_csv(self) -> dict[str, object]:
        with self._lock:
            if self._capture_active:
                raise ValueError(
                    "Cannot reset the CSV while a gathering session is active.")

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with self._csv_lock:
            with self._data_file.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(CSV_HEADER)

        with self._lock:
            self._sample_count = 0
            self._last_sample = []
            self._clear_analysis_results_locked()
            self._status_message = "The calibration CSV has been reset."
            self._updated_at = self._timestamp_label()
            return self.status_payload()

    def csv_file_path(self) -> Path:
        if not self._data_file.exists():
            raise ValueError("No calibration CSV exists yet.")
        return self._data_file

    def run_analysis(self) -> dict[str, object]:
        with self._lock:
            if self._capture_active:
                raise ValueError(
                    "Stop the current gathering session before running centroid analysis.")

        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        result = run_centroid_analysis(self._data_file, GENERATED_STATIC_DIR)

        with self._lock:
            self._analysis_error = None
            self._analysis_cpp_code = str(result["cpp_code"])
            self._analysis_plot_links = list(result["plot_links"])
            self._analysis_unknown_threshold = float(
                result["unknown_threshold"])
            silhouette_score = result["silhouette_score"]
            self._analysis_silhouette_score = (
                None if silhouette_score is None else float(silhouette_score)
            )
            self._analysis_sample_count = int(result["sample_count"])
            self._analysis_class_sizes = dict(result["class_sizes"])
            self._analysis_message = (
                f"Centroid analysis complete. {self._analysis_sample_count} samples processed."
            )
            self._status_message = self._analysis_message
            self._updated_at = self._timestamp_label()
            return self.status_payload()

    def reset_arduino(self) -> dict[str, object]:
        with self._lock:
            capture_was_active = self._capture_active

        if capture_was_active:
            try:
                self._call_bridge(BRIDGE_STOP_METHOD)
            except RuntimeError:
                logger.warning(
                    "Bridge stop failed while preparing Arduino reset.")
            with self._lock:
                self._capture_active = False
                self._status_message = "Capture stopped before resetting the Arduino."

        try:
            completed = subprocess.run(
                ARDUINO_RESET_COMMAND,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "The 'arduino-reset' command is not available on this system.") from error
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                "The 'arduino-reset' command timed out.") from error

        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            stdout = completed.stdout.strip()
            detail = stderr or stdout or f"exit code {completed.returncode}"
            raise RuntimeError(f"The 'arduino-reset' command failed: {detail}")

        self._refresh_sensor_ready()
        with self._lock:
            self._status_message = "Arduino reset command completed."
            self._updated_at = self._timestamp_label()
            return self.status_payload()

    def _finish_capture_after_target(self) -> None:
        try:
            self._call_bridge(BRIDGE_STOP_METHOD)
            with self._lock:
                color_name = self._selected_color or "selected"
                self._status_message = (
                    f"Capture complete for {color_name}. {self._target_samples} samples saved."
                )
                self._updated_at = self._timestamp_label()
        except RuntimeError as error:
            self._set_bridge_error(str(error))

    def _register_bridge_handler(self) -> None:
        try:
            Bridge.provide(BRIDGE_SAMPLE_METHOD, self.handle_color_sample)
            self._refresh_sensor_ready()
            with self._lock:
                self._bridge_connected = True
                self._bridge_last_error = None
                if not self._capture_active:
                    self._status_message = "Bridge connected. Select a color to start gathering."
                self._updated_at = self._timestamp_label()
            logger.info("Registered Bridge handler for %s",
                        BRIDGE_SAMPLE_METHOD)
        except Exception as error:
            self._set_bridge_error(
                f"Failed to register bridge handler: {error}")

    def _refresh_sensor_ready(self) -> None:
        try:
            sensor_ready = bool(self._call_bridge(BRIDGE_SENSOR_READY_METHOD))
        except RuntimeError as error:
            self._set_bridge_error(str(error))
            return

        with self._lock:
            self._bridge_connected = True
            self._bridge_last_error = None
            self._sensor_ready = sensor_ready
            self._updated_at = self._timestamp_label()

    def _call_bridge(self, method_name: str, *params: object) -> object:
        try:
            return Bridge.call(method_name, *params, timeout=3)
        except Exception as error:
            raise RuntimeError(
                f"Bridge call '{method_name}' failed: {error}") from error

    def _append_csv_row(self, color_name: str, sample: list[int]) -> None:
        with self._csv_lock:
            with self._data_file.open("a", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow([color_name, *sample])

    def _ensure_csv_header(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with self._csv_lock:
            needs_header = not self._data_file.exists() or self._data_file.stat().st_size == 0
            if not needs_header:
                return

            with self._data_file.open("a", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(CSV_HEADER)

    def _clear_analysis_results_locked(self) -> None:
        self._analysis_message = "No centroid analysis has been run yet."
        self._analysis_error = None
        self._analysis_cpp_code = ""
        self._analysis_plot_links = []
        self._analysis_unknown_threshold = None
        self._analysis_silhouette_score = None
        self._analysis_sample_count = 0
        self._analysis_class_sizes = {}

    def _badge_for_color(self, color_name: str | None) -> str:
        if color_name is None:
            return "text-bg-secondary"
        return COLOR_BADGES.get(color_name, "text-bg-secondary")

    def _set_bridge_error(self, message: str) -> None:
        logger.error(message)
        with self._lock:
            self._bridge_last_error = message
            self._bridge_connected = False
            self._sensor_ready = False
            self._status_message = message
            self._updated_at = self._timestamp_label()

    def _timestamp_label(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
