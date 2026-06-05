from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock, Thread

from bridge import Bridge
from logger import Logger

from .config import (
    BRIDGE_SAMPLE_METHOD,
    BRIDGE_SENSOR_READY_METHOD,
    BRIDGE_START_METHOD,
    BRIDGE_STOP_METHOD,
    CAPTURE_COLORS,
    CAPTURE_TARGET_SAMPLES,
    COLOR_BADGES,
    DATA_DIR,
    DATA_FILE,
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
                "updated_at": self._updated_at,
            }
            return payload

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
                writer.writerow(
                    ["color_name", *[f"channel{index}" for index in range(1, 11)]])

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
