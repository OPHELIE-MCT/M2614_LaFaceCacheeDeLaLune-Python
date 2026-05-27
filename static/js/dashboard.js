(function () {
    const THEME_KEY = "m2614-theme";
    const DASHBOARD_ENDPOINT = "/api/dashboard";
    const SORTING_ENDPOINT = "/api/control/sorting";
    const MODE_ENDPOINT = "/api/control/mode";
    const CALIBRATION_ENDPOINT = "/api/control/calibrations";
    const REFRESH_INTERVAL_MS = 5000;

    const moonIcon = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">',
        '<path d="M6 0a6.25 6.25 0 1 0 8.55 8.72A7 7 0 1 1 6 0Z" />',
        "</svg>",
    ].join("");

    const sunIcon = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">',
        '<path d="M8 3.25a.75.75 0 0 1 .75.75v.5a.75.75 0 0 1-1.5 0V4A.75.75 0 0 1 8 3.25Zm0 7.25a.75.75 0 0 1 .75.75v.5a.75.75 0 0 1-1.5 0v-.5A.75.75 0 0 1 8 10.5ZM12 7.25a.75.75 0 0 1 0 1.5h-.5a.75.75 0 0 1 0-1.5h.5ZM4.5 7.25a.75.75 0 0 1 0 1.5H4a.75.75 0 0 1 0-1.5h.5ZM10.56 4.38a.75.75 0 0 1 1.06 0l.35.35a.75.75 0 0 1-1.06 1.06l-.35-.35a.75.75 0 0 1 0-1.06Zm-6.18 6.18a.75.75 0 0 1 1.06 0l.35.35a.75.75 0 1 1-1.06 1.06l-.35-.35a.75.75 0 0 1 0-1.06Zm7.59 1.41a.75.75 0 0 1-1.06 0l-.35-.35a.75.75 0 0 1 1.06-1.06l.35.35a.75.75 0 0 1 0 1.06Zm-6.88-6.88a.75.75 0 0 1-1.06 0l-.35-.35a.75.75 0 1 1 1.06-1.06l.35.35a.75.75 0 0 1 0 1.06ZM8 5.5A2.5 2.5 0 1 0 8 10.5 2.5 2.5 0 0 0 8 5.5Z" />',
        "</svg>",
    ].join("");

    let toastInstance;

    function initTheme() {
        const savedTheme = localStorage.getItem(THEME_KEY);
        const systemPrefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        const theme = savedTheme || (systemPrefersDark ? "dark" : "light");
        applyTheme(theme);
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-bs-theme", theme);
        const nextTheme = theme === "dark" ? "light" : "dark";

        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            const label = button.querySelector("[data-theme-label]");
            const icon = button.querySelector("[data-theme-icon]");

            if (label) {
                label.textContent = nextTheme === "dark" ? "Dark theme" : "Light theme";
            }

            if (icon) {
                icon.innerHTML = nextTheme === "dark" ? moonIcon : sunIcon;
            }

            button.setAttribute("aria-label", `Switch to ${nextTheme} theme`);
        });

        drawLidarPlaceholder();
    }

    function bindThemeToggle() {
        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            button.addEventListener("click", function () {
                const currentTheme = document.documentElement.getAttribute("data-bs-theme") || "light";
                const nextTheme = currentTheme === "dark" ? "light" : "dark";
                localStorage.setItem(THEME_KEY, nextTheme);
                applyTheme(nextTheme);
            });
        });
    }

    async function refreshDashboard() {
        try {
            const response = await fetch(DASHBOARD_ENDPOINT, { headers: { Accept: "application/json" } });
            if (!response.ok) {
                throw new Error(`Dashboard refresh failed with status ${response.status}`);
            }

            const payload = await response.json();
            renderDashboard(payload);
        } catch (error) {
            showToast(error.message, "danger");
        }
    }

    function renderDashboard(payload) {
        updateText('[data-system-metric="cpu"]', formatPercent(payload.system.cpu_percent));
        updateText('[data-system-metric="ram"]', formatPercent(payload.system.ram_percent));
        updateText('[data-field="ball-count"]', payload.sorter.ball_count);
        updateText('[data-field="ball-color"]', payload.sorter.current_ball.label);
        updateText('[data-field="ball-confidence"]', `${payload.sorter.current_ball.confidence}%`);
        updateText('[data-field="robot-status-note"]', payload.robot.status_note);
        updateText('[data-field="last-action"]', payload.meta.last_action);
        updateText('[data-field="sorting-status-text"]', payload.sorter.enabled ? "Armed" : "Standby");
        updateText('[data-field="robot-summary"]', payload.robot.summary);
        updateText('[data-field="lidar-scan-id"]', payload.lidar.scan_id);
        updateText('[data-field="lidar-frequency"]', `${payload.lidar.frequency_hz} Hz`);
        updateText('[data-field="lidar-status-text"]', payload.lidar.message);

        document.querySelectorAll('[data-field="robot-mode-badge"], [data-field="robot-mode-chip"]').forEach((element) => {
            element.textContent = payload.robot.current_mode.label;
            element.className = `badge rounded-pill ${payload.robot.current_mode.badge_class}`;
        });

        document.querySelectorAll('[data-field="ball-color"]').forEach((element) => {
            element.className = `badge rounded-pill ${payload.sorter.current_ball.badge_class}`;
        });

        document.querySelectorAll('[data-field="ball-confidence-bar"]').forEach((element) => {
            element.className = `progress-bar ${payload.sorter.current_ball.progress_class}`;
            element.style.width = `${payload.sorter.current_ball.confidence}%`;
            element.textContent = `${payload.sorter.current_ball.confidence}%`;
        });

        payload.robot.flags.forEach((flag) => {
            document.querySelectorAll(`[data-flag="${flag.key}"]`).forEach((element) => {
                element.textContent = flag.state_label;
                element.className = `badge rounded-pill ${flag.badge_class}`;
            });
        });

        updateModeSelector(payload.modes);
        updateSortingToggle(payload.robot.sorting_forced);
        updateEventLog(payload.events);
        drawLidarPlaceholder(payload.lidar);
    }

    function updateModeSelector(modes) {
        document.querySelectorAll("[data-mode-option]").forEach((button) => {
            const currentMode = modes.find((mode) => mode.key === button.dataset.modeOption);
            if (!currentMode) {
                return;
            }

            button.classList.toggle("active", currentMode.is_active);
            const badge = button.querySelector(".badge");
            if (badge) {
                badge.className = currentMode.is_active ? "badge text-bg-light" : "badge text-bg-dark";
                badge.textContent = currentMode.is_active ? "Active" : "Ready";
            }
        });
    }

    function updateSortingToggle(isChecked) {
        document.querySelectorAll("[data-sorting-toggle]").forEach((input) => {
            input.checked = isChecked;
        });
    }

    function updateEventLog(events) {
        document.querySelectorAll("[data-event-log]").forEach((container) => {
            container.innerHTML = "";

            events.forEach((event) => {
                const item = document.createElement("div");
                item.className = "list-group-item px-0 py-3";
                item.innerHTML = `
                    <div class="d-flex justify-content-between align-items-start gap-3">
                        <div>
                            <p class="mb-1 fw-semibold">${escapeHtml(event.message)}</p>
                            <p class="mb-0 small text-body-secondary">${escapeHtml(event.timestamp)}</p>
                        </div>
                        <span class="badge rounded-pill ${escapeHtml(event.badge_class)}">Event</span>
                    </div>
                `;
                container.appendChild(item);
            });
        });
    }

    function bindControls() {
        document.addEventListener("click", async function (event) {
            const calibrationButton = event.target.closest("[data-calibration]");
            if (calibrationButton) {
                await postJson(`${CALIBRATION_ENDPOINT}/${calibrationButton.dataset.calibration}`, {});
                return;
            }

            const modeButton = event.target.closest("[data-mode-option]");
            if (modeButton) {
                await postJson(MODE_ENDPOINT, { mode: modeButton.dataset.modeOption });
            }
        });

        document.querySelectorAll("[data-sorting-toggle]").forEach((input) => {
            input.addEventListener("change", async function () {
                await postJson(SORTING_ENDPOINT, { enabled: input.checked });
            });
        });
    }

    async function postJson(url, payload) {
        try {
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
                    return { detail: `Request failed with status ${response.status}` };
                });
                throw new Error(errorPayload.detail || `Request failed with status ${response.status}`);
            }

            const result = await response.json();
            renderDashboard(result.dashboard);
            showToast(result.message, "success");
        } catch (error) {
            showToast(error.message, "danger");
            refreshDashboard();
        }
    }

    function showToast(message, variant) {
        const toastElement = document.getElementById("dashboardToast");
        if (!toastElement || !window.bootstrap) {
            return;
        }

        toastElement.className = `toast align-items-center text-bg-${variant || "dark"} border-0`;
        const body = toastElement.querySelector(".toast-body");
        if (body) {
            body.textContent = message;
        }

        toastInstance = toastInstance || new window.bootstrap.Toast(toastElement, { delay: 2800 });
        toastInstance.show();
    }

    function drawLidarPlaceholder(lidarPayload) {
        const canvas = document.getElementById("lidarCanvas");
        if (!canvas) {
            return;
        }

        const width = canvas.clientWidth;
        const height = canvas.clientHeight;
        if (!width || !height) {
            return;
        }

        const ratio = window.devicePixelRatio || 1;
        canvas.width = Math.floor(width * ratio);
        canvas.height = Math.floor(height * ratio);

        const ctx = canvas.getContext("2d");
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        ctx.clearRect(0, 0, width, height);

        const isDark = document.documentElement.getAttribute("data-bs-theme") === "dark";
        const gridColor = isDark ? "rgba(251, 146, 60, 0.22)" : "rgba(217, 119, 6, 0.22)";
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(width, height) * 0.34;

        ctx.strokeStyle = gridColor;
        ctx.lineWidth = 1;

        for (let ring = 1; ring <= 4; ring += 1) {
            ctx.beginPath();
            ctx.arc(centerX, centerY, (radius / 4) * ring, 0, Math.PI * 2);
            ctx.stroke();
        }

        ctx.beginPath();
        ctx.moveTo(centerX, centerY - radius);
        ctx.lineTo(centerX, centerY + radius);
        ctx.moveTo(centerX - radius, centerY);
        ctx.lineTo(centerX + radius, centerY);
        ctx.stroke();

        ctx.fillStyle = isDark ? "rgba(248, 250, 252, 0.88)" : "rgba(15, 23, 42, 0.8)";
        ctx.font = '600 16px "Segoe UI Variable", "Segoe UI", sans-serif';
        ctx.textAlign = "center";
        ctx.fillText("LiDAR live map reserved", centerX, centerY - 8);
        ctx.font = '400 13px "Segoe UI Variable", "Segoe UI", sans-serif';
        ctx.fillText(
            lidarPayload && lidarPayload.message ? lidarPayload.message : "Placeholder canvas awaiting scan stream",
            centerX,
            centerY + 18,
        );
    }

    function updateText(selector, value) {
        document.querySelectorAll(selector).forEach((element) => {
            element.textContent = value;
        });
    }

    function formatPercent(value) {
        return `${Number(value).toFixed(1)}%`;
    }

    function escapeHtml(value) {
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    document.addEventListener("DOMContentLoaded", function () {
        initTheme();
        bindThemeToggle();
        bindControls();
        refreshDashboard();
        window.setInterval(refreshDashboard, REFRESH_INTERVAL_MS);
        window.addEventListener("resize", function () {
            drawLidarPlaceholder();
        });
    });
})();