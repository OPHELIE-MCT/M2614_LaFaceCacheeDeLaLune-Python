from __future__ import annotations

import csv
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock, Thread

from bridge import Bridge
from logger import Logger

from .config import (
    ANALYSIS_DIR,
    ANALYSIS_RESULT_FILE,
    ARDUINO_RESET_COMMAND,
    BRIDGE_SAMPLE_METHOD,
    BRIDGE_SENSOR_READY_METHOD,
    BRIDGE_AUTONOMOUS_GET_METHOD,
    BRIDGE_AUTONOMOUS_SET_METHOD,
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
        self._bridge_supported = platform.system() == "Linux"
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
        self._autonomous_mode_enabled = False
        self._autonomous_mode_error: str | None = None
        self._analysis_message = "No centroid analysis has been run yet."
        self._analysis_error: str | None = None
        self._analysis_running = False
        self._analysis_cpp_code = ""
        self._analysis_plot_links: list[dict[str, str]] = []
        self._analysis_unknown_threshold: float | None = None
        self._analysis_inner_confidence_radius: float | None = None
        self._analysis_outer_confidence_radii: dict[str, float] = {}
        self._analysis_nearest_centroid_distances: dict[str, float] = {}
        self._analysis_silhouette_score: float | None = None
        self._analysis_sample_count = 0
        self._analysis_class_sizes: dict[str, int] = {}
        self._analysis_result_file = ANALYSIS_RESULT_FILE
        self._load_analysis_results()

        if self._bridge_supported:
            bridge_thread = Thread(
                target=self._register_bridge_handler,
                name="BridgeRegister",
                daemon=True,
            )
            bridge_thread.start()
        else:
            self._status_message = (
                "Bridge functions are unavailable on this platform. Run the app on the Uno Q Linux SBC."
            )

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
                "autonomous_mode_enabled": self._autonomous_mode_enabled,
                "autonomous_mode_error": self._autonomous_mode_error,
                "autonomous_mode_supported": self._bridge_supported,
                "analysis_message": self._analysis_message,
                "analysis_error": self._analysis_error,
                "analysis_running": self._analysis_running,
                "analysis_cpp_code": self._analysis_cpp_code,
                "analysis_plot_links": list(self._analysis_plot_links),
                "analysis_unknown_threshold": self._analysis_unknown_threshold,
                "analysis_inner_confidence_radius": self._analysis_inner_confidence_radius,
                "analysis_outer_confidence_radii": dict(self._analysis_outer_confidence_radii),
                "analysis_nearest_centroid_distances": dict(self._analysis_nearest_centroid_distances),
                "analysis_silhouette_score": self._analysis_silhouette_score,
                "analysis_sample_count": self._analysis_sample_count,
                "analysis_class_sizes": dict(self._analysis_class_sizes),
                "updated_at": self._updated_at,
            }
            return payload

    def poll_status(self) -> dict[str, object]:
        if not self._bridge_supported:
            return self.status_payload()

        self._refresh_sensor_ready()
        self._refresh_autonomous_mode()
        return self.status_payload()

    def set_autonomous_mode(self, enabled: bool) -> dict[str, object]:
        """Toggle the robot autonomous fallback through RouterBridge.

        @param enabled True to enable the autonomous fallback on RC signal loss.
        @return Updated status payload.
        @raises RuntimeError when the bridge is unavailable or the call fails.
        """
        if not self._bridge_supported:
            raise RuntimeError(
                "Bridge is unavailable on this platform. Run the app on the Uno Q Linux SBC."
            )

        try:
            self._call_bridge(BRIDGE_AUTONOMOUS_SET_METHOD,
                              1 if enabled else 0)
        except RuntimeError as error:
            with self._lock:
                self._autonomous_mode_error = str(error)
                self._updated_at = self._timestamp_label()
            raise

        with self._lock:
            self._autonomous_mode_enabled = bool(enabled)
            self._autonomous_mode_error = None
            self._updated_at = self._timestamp_label()
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
            if self._analysis_running:
                raise ValueError("Centroid analysis is already running.")
            self._analysis_running = True
            self._analysis_error = None
            self._analysis_message = "Centroid analysis is running..."
            self._status_message = self._analysis_message
            self._updated_at = self._timestamp_label()

        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            from .centroid_analysis import run_centroid_analysis
            result = run_centroid_analysis(
                self._data_file, GENERATED_STATIC_DIR)
        except (ImportError, OSError) as error:
            with self._lock:
                self._analysis_running = False
                self._analysis_error = str(error)
                self._analysis_message = "Centroid analysis dependencies are unavailable."
                self._status_message = self._analysis_message
                self._updated_at = self._timestamp_label()
            raise RuntimeError(
                "Centroid analysis dependencies could not be loaded. "
                "Install a compatible scipy/scikit-learn build for this platform."
            ) from error
        except Exception as error:
            with self._lock:
                self._analysis_running = False
                self._analysis_error = str(error)
                self._analysis_message = "Centroid analysis failed."
                self._status_message = self._analysis_message
                self._updated_at = self._timestamp_label()
            raise

        with self._lock:
            self._analysis_running = False
            self._analysis_error = None
            self._analysis_cpp_code = str(result["cpp_code"])
            self._analysis_plot_links = list(result["plot_links"])
            self._analysis_unknown_threshold = float(
                result["unknown_threshold"])
            inner_confidence_radius = result.get(
                "inner_confidence_radius", result["unknown_threshold"]
            )
            self._analysis_inner_confidence_radius = float(
                inner_confidence_radius)
            self._analysis_outer_confidence_radii = {
                str(label): float(radius)
                for label, radius in dict(result.get("outer_confidence_radii") or {}).items()
            }
            self._analysis_nearest_centroid_distances = {
                str(label): float(distance)
                for label, distance in dict(result.get("nearest_centroid_distances") or {}).items()
            }
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
            self._save_analysis_results_locked()
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
        if not self._bridge_supported:
            with self._lock:
                self._bridge_connected = False
                self._sensor_ready = False
                self._bridge_last_error = None
                self._updated_at = self._timestamp_label()
            return

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

    def _refresh_autonomous_mode(self) -> None:
        if not self._bridge_supported:
            return

        try:
            enabled = bool(self._call_bridge(BRIDGE_AUTONOMOUS_GET_METHOD))
        except RuntimeError as error:
            with self._lock:
                self._autonomous_mode_error = str(error)
                self._updated_at = self._timestamp_label()
            return

        with self._lock:
            self._autonomous_mode_enabled = enabled
            self._autonomous_mode_error = None
            self._updated_at = self._timestamp_label()

    def _call_bridge(self, method_name: str, *params: object) -> object:
        if not self._bridge_supported:
            raise RuntimeError(
                "Bridge is unavailable on this platform. Run the app on the Uno Q Linux SBC."
            )

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
        self._analysis_running = False
        self._analysis_cpp_code = ""
        self._analysis_plot_links = []
        self._analysis_unknown_threshold = None
        self._analysis_inner_confidence_radius = None
        self._analysis_outer_confidence_radii = {}
        self._analysis_nearest_centroid_distances = {}
        self._analysis_silhouette_score = None
        self._analysis_sample_count = 0
        self._analysis_class_sizes = {}
        self._delete_saved_analysis_results_locked()

    def _load_analysis_results(self) -> None:
        if not self._analysis_result_file.exists():
            return

        try:
            with self._analysis_result_file.open("r", encoding="utf-8") as results_file:
                payload = json.load(results_file)
        except (OSError, json.JSONDecodeError) as error:
            logger.warning(
                "Failed to load saved centroid analysis results: %s", error)
            return

        try:
            self._analysis_cpp_code = str(payload.get("cpp_code") or "")
            self._analysis_plot_links = [
                {"label": str(plot["label"]), "href": str(plot["href"])}
                for plot in payload.get("plot_links", [])
                if "label" in plot and "href" in plot
            ]
            unknown_threshold = payload.get("unknown_threshold")
            self._analysis_unknown_threshold = (
                None if unknown_threshold is None else float(unknown_threshold)
            )
            inner_confidence_radius = payload.get("inner_confidence_radius")
            if inner_confidence_radius is None:
                self._analysis_inner_confidence_radius = self._analysis_unknown_threshold
            else:
                self._analysis_inner_confidence_radius = float(
                    inner_confidence_radius)
            self._analysis_outer_confidence_radii = {
                str(label): float(radius)
                for label, radius in dict(payload.get("outer_confidence_radii") or {}).items()
            }
            self._analysis_nearest_centroid_distances = {
                str(label): float(distance)
                for label, distance in dict(payload.get("nearest_centroid_distances") or {}).items()
            }
            silhouette_score = payload.get("silhouette_score")
            self._analysis_silhouette_score = (
                None if silhouette_score is None else float(silhouette_score)
            )
            self._analysis_sample_count = int(payload.get("sample_count") or 0)
            self._analysis_class_sizes = {
                str(label): int(count)
                for label, count in dict(payload.get("class_sizes") or {}).items()
            }
            saved_at = str(payload.get("saved_at") or self._timestamp_label())
            self._updated_at = saved_at
            self._analysis_message = (
                f"Loaded saved centroid analysis. {self._analysis_sample_count} samples processed."
            )
        except (TypeError, ValueError, KeyError) as error:
            logger.warning(
                "Saved centroid analysis results are invalid: %s", error)

    def _save_analysis_results_locked(self) -> None:
        payload = {
            "cpp_code": self._analysis_cpp_code,
            "plot_links": self._analysis_plot_links,
            "unknown_threshold": self._analysis_unknown_threshold,
            "inner_confidence_radius": self._analysis_inner_confidence_radius,
            "outer_confidence_radii": self._analysis_outer_confidence_radii,
            "nearest_centroid_distances": self._analysis_nearest_centroid_distances,
            "silhouette_score": self._analysis_silhouette_score,
            "sample_count": self._analysis_sample_count,
            "class_sizes": self._analysis_class_sizes,
            "saved_at": self._updated_at,
        }
        try:
            self._analysis_result_file.parent.mkdir(
                parents=True, exist_ok=True)
            with self._analysis_result_file.open("w", encoding="utf-8") as results_file:
                json.dump(payload, results_file, indent=2)
                results_file.write("\n")
        except OSError as error:
            logger.warning(
                "Failed to save centroid analysis results: %s", error)

    def _delete_saved_analysis_results_locked(self) -> None:
        try:
            self._analysis_result_file.unlink(missing_ok=True)
        except OSError as error:
            logger.warning(
                "Failed to delete saved centroid analysis results: %s", error)

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
