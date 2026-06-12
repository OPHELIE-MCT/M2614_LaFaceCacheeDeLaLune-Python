(function () {
    const STATUS_ENDPOINT = "/api/gather/status";
    const START_ENDPOINT = "/api/gather/start";
    const STOP_ENDPOINT = "/api/gather/stop";
    const RESET_CSV_ENDPOINT = "/api/gather/csv/reset";
    const RUN_ANALYSIS_ENDPOINT = "/api/gather/analysis/run";
    const RESET_ARDUINO_ENDPOINT = "/api/gather/device/reset";
    const REFRESH_INTERVAL_MS = 1000;

    let toastInstance;

    function updateStatus(payload, options) {
        const shouldUpdateAnalysisCode = options && options.updateAnalysisCode;

        updateText('[data-field="status-message"]', payload.status_message);
        updateText('[data-field="sample-count"]', payload.sample_count);
        updateText('[data-field="target-samples"]', payload.target_samples);
        updateText('[data-field="csv-path"]', payload.csv_path);
        updateText('[data-field="updated-at"]', payload.updated_at);
        updateText('[data-field="bridge-error"]', payload.bridge_error || "No bridge errors.");
        updateText('[data-field="bridge-label"]', payload.bridge_connected ? "Connected" : "Waiting for router");
        updateText(
            '[data-field="sensor-label"]',
            payload.sensor_ready
                ? "AS7341 detected on Wire1. Calibration mode is available."
                : "AS7341 disconnected. The robot can keep running its normal firmware mode.",
        );
        updateText('[data-field="selected-color-badge"]', payload.selected_color || "none");
        updateText('[data-field="analysis-message"]', payload.analysis_message || "No centroid analysis has been run yet.");
        updateText('[data-field="analysis-error"]', payload.analysis_error || "");
        if (shouldUpdateAnalysisCode) {
            updateText(
                '[data-field="analysis-cpp-code"]',
                payload.analysis_cpp_code || "Run centroid analysis to generate the C++ array.",
            );
        }
        updateText(
            '[data-field="analysis-summary"]',
            payload.analysis_sample_count
                ? `${payload.analysis_sample_count} samples processed.`
                : "Run centroid analysis to save plots locally on the Uno Q SBC.",
        );
        updateText(
            '[data-field="analysis-threshold"]',
            typeof payload.analysis_unknown_threshold === "number"
                ? `Unknown threshold: ${payload.analysis_unknown_threshold.toFixed(8)}`
                : "Unknown threshold unavailable.",
        );
        updateText(
            '[data-field="analysis-silhouette"]',
            typeof payload.analysis_silhouette_score === "number"
                ? `Silhouette score: ${payload.analysis_silhouette_score.toFixed(3)}`
                : "Silhouette score unavailable.",
        );
        updateText(
            '[data-field="last-sample"]',
            payload.last_sample && payload.last_sample.length > 0
                ? payload.last_sample.join(", ")
                : "No sample received yet.",
        );
        updatePlotLinks(payload.analysis_plot_links || []);

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
            if (payload.capture_active && payload.selected_color) {
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
            updateStatus(payload, { updateAnalysisCode: false });
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

    async function resetCsv() {
        await postJson(RESET_CSV_ENDPOINT, {});
    }

    async function runAnalysis() {
        await postJson(RUN_ANALYSIS_ENDPOINT, {}, { updateAnalysisCode: true });
    }

    async function resetArduino() {
        await postJson(RESET_ARDUINO_ENDPOINT, {});
    }

    async function postJson(url, payload, statusOptions) {
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
        updateStatus(result.status, statusOptions || { updateAnalysisCode: true });
        showToast(result.message, "success");
    }

    async function copyAnalysisCode() {
        const codeElement = document.querySelector('[data-field="analysis-cpp-code"]');
        const codeText = codeElement ? codeElement.textContent.trim() : "";
        if (!codeText) {
            showToast("No C++ code available to copy.", "warning");
            return;
        }

        try {
            await writeClipboardText(codeText);
            showToast("C++ code copied to clipboard.", "success");
        } catch (error) {
            showToast(error.message || "Copy to clipboard failed.", "danger");
        }
    }

    async function writeClipboardText(text) {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
            return;
        }

        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.setAttribute("readonly", "");
        textArea.style.position = "fixed";
        textArea.style.top = "-9999px";
        textArea.style.left = "-9999px";
        document.body.appendChild(textArea);
        textArea.select();

        try {
            const copied = document.execCommand("copy");
            if (!copied) {
                throw new Error("Copy to clipboard failed.");
            }
        } finally {
            document.body.removeChild(textArea);
        }
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

        document.querySelectorAll("[data-reset-csv-button]").forEach((button) => {
            button.addEventListener("click", async function () {
                if (!window.confirm("Reset the calibration CSV and erase all captured samples?")) {
                    return;
                }

                try {
                    await resetCsv();
                } catch (error) {
                    showToast(error.message, "danger");
                }
            });
        });

        document.querySelectorAll("[data-run-analysis-button]").forEach((button) => {
            button.addEventListener("click", async function () {
                try {
                    await runAnalysis();
                } catch (error) {
                    showToast(error.message, "danger");
                }
            });
        });

        document.querySelectorAll("[data-reset-arduino-button]").forEach((button) => {
            button.addEventListener("click", async function () {
                try {
                    await resetArduino();
                } catch (error) {
                    showToast(error.message, "danger");
                }
            });
        });

        document.querySelectorAll("[data-copy-analysis-code-button]").forEach((button) => {
            button.addEventListener("click", copyAnalysisCode);
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

    function updatePlotLinks(plotLinks) {
        document.querySelectorAll('[data-field="analysis-plot-links"]').forEach((element) => {
            element.innerHTML = "";

            if (!plotLinks.length) {
                const item = document.createElement("li");
                item.textContent = "No plots generated yet.";
                element.appendChild(item);
                return;
            }

            plotLinks.forEach((plot) => {
                const item = document.createElement("li");
                const link = document.createElement("a");
                link.href = plot.href;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.textContent = plot.label;
                item.appendChild(link);
                element.appendChild(item);
            });
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        bindEvents();
        refreshStatus();
        window.setInterval(refreshStatus, REFRESH_INTERVAL_MS);
    });
})();