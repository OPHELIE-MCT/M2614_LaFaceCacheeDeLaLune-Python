(function () {
    const STATUS_ENDPOINT = "/api/gather/status";
    const START_ENDPOINT = "/api/gather/start";
    const STOP_ENDPOINT = "/api/gather/stop";
    const REFRESH_INTERVAL_MS = 1000;

    let toastInstance;

    function updateStatus(payload) {
        updateText('[data-field="status-message"]', payload.status_message);
        updateText('[data-field="sample-count"]', payload.sample_count);
        updateText('[data-field="target-samples"]', payload.target_samples);
        updateText('[data-field="csv-path"]', payload.csv_path);
        updateText('[data-field="updated-at"]', payload.updated_at);
        updateText('[data-field="bridge-error"]', payload.bridge_error || "No bridge errors.");
        updateText('[data-field="bridge-label"]', payload.bridge_connected ? "Connected" : "Waiting for router");
        updateText('[data-field="sensor-label"]', payload.sensor_ready ? "AS7341 detected on Wire1." : "AS7341 not ready yet.");
        updateText('[data-field="selected-color-badge"]', payload.selected_color || "none");
        updateText(
            '[data-field="last-sample"]',
            payload.last_sample && payload.last_sample.length > 0
                ? payload.last_sample.join(", ")
                : "No sample received yet.",
        );

        document.querySelectorAll("[data-bridge-dot]").forEach((element) => {
            element.classList.toggle("status-dot-live", payload.bridge_connected);
            element.classList.toggle("status-dot-offline", !payload.bridge_connected);
        });

        document.querySelectorAll("[data-start-button]").forEach((button) => {
            button.disabled = payload.capture_active;
        });

        document.querySelectorAll("[data-stop-button]").forEach((button) => {
            button.disabled = !payload.capture_active;
        });

        document.querySelectorAll("[data-field=" + JSON.stringify("selected-color-badge") + "]").forEach((element) => {
            element.className = `badge rounded-pill ${payload.selected_color_badge}`;
        });

        document.querySelectorAll('[data-field="progress-bar"]').forEach((element) => {
            const percentage = payload.target_samples === 0
                ? 0
                : Math.min(100, (payload.sample_count / payload.target_samples) * 100);
            element.style.width = `${percentage}%`;
        });

        document.querySelectorAll("[data-color-select]").forEach((select) => {
            if (!payload.capture_active && payload.selected_color) {
                select.value = payload.selected_color;
            }
        });
    }

    async function refreshStatus() {
        try {
            const response = await fetch(STATUS_ENDPOINT, { headers: { Accept: "application/json" } });
            if (!response.ok) {
                throw new Error(`Status refresh failed with ${response.status}`);
            }

            const payload = await response.json();
            updateStatus(payload);
        } catch (error) {
            showToast(error.message, "danger");
        }
    }

    async function startGathering(colorName) {
        await postJson(START_ENDPOINT, { color: colorName });
    }

    async function stopGathering() {
        await postJson(STOP_ENDPOINT, {});
    }

    async function postJson(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const errorPayload = await response.json().catch(function () {
                return { detail: `Request failed with ${response.status}` };
            });
            throw new Error(errorPayload.detail || `Request failed with ${response.status}`);
        }

        const result = await response.json();
        updateStatus(result.status);
        showToast(result.message, "success");
    }

    function bindEvents() {
        document.querySelectorAll("[data-gather-form]").forEach((form) => {
            form.addEventListener("submit", async function (event) {
                event.preventDefault();
                const select = form.querySelector("[data-color-select]");
                if (!select) {
                    return;
                }

                try {
                    await startGathering(select.value);
                } catch (error) {
                    showToast(error.message, "danger");
                }
            });
        });

        document.querySelectorAll("[data-stop-button]").forEach((button) => {
            button.addEventListener("click", async function () {
                try {
                    await stopGathering();
                } catch (error) {
                    showToast(error.message, "danger");
                }
            });
        });
    }

    function showToast(message, variant) {
        const toastElement = document.getElementById("gatherToast");
        if (!toastElement || !window.bootstrap) {
            return;
        }

        toastElement.className = `toast align-items-center text-bg-${variant || "dark"} border-0`;
        const body = toastElement.querySelector(".toast-body");
        if (body) {
            body.textContent = message;
        }

        toastInstance = toastInstance || new window.bootstrap.Toast(toastElement, { delay: 2500 });
        toastInstance.show();
    }

    function updateText(selector, value) {
        document.querySelectorAll(selector).forEach((element) => {
            element.textContent = value;
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        bindEvents();
        refreshStatus();
        window.setInterval(refreshStatus, REFRESH_INTERVAL_MS);
    });
})();