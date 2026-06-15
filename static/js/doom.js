(function () {
    function updateStatus(statusElement, message, tone) {
        if (!statusElement) {
            return;
        }

        statusElement.textContent = message;
        statusElement.dataset.tone = tone;
    }

    document.addEventListener("DOMContentLoaded", function () {
        const playerElement = document.querySelector("[data-doom-player]");
        if (!playerElement) {
            return;
        }

        const statusElement = document.querySelector("[data-doom-status]");
        const fullscreenButton = document.querySelector("[data-doom-fullscreen]");
        const restartButton = document.querySelector("[data-doom-restart]");
        const dosFactory = globalThis.Dos;

        if (typeof dosFactory !== "function") {
            updateStatus(statusElement, "The js-dos runtime failed to load.", "danger");
            return;
        }

        let dosProps;

        if (restartButton) {
            restartButton.addEventListener("click", function () {
                window.location.reload();
            });
        }

        if (fullscreenButton) {
            fullscreenButton.addEventListener("click", function () {
                if (!dosProps) {
                    return;
                }
                dosProps.setFullScreen(true);
            });
        }

        updateStatus(statusElement, "Booting DOOM shareware...", "loading");

        try {
            dosProps = dosFactory(playerElement, {
                url: playerElement.dataset.bundleUrl,
                pathPrefix: playerElement.dataset.pathPrefix,
                autoStart: true,
                kiosk: true,
                mouseCapture: true,
                thinSidebar: true,
                imageRendering: "pixelated",
                renderAspect: "4/3",
                onEvent: function (eventName) {
                    if (eventName === "ci-ready") {
                        if (fullscreenButton) {
                            fullscreenButton.disabled = false;
                        }
                        updateStatus(
                            statusElement,
                            "DOOM is ready. Click the game to capture input.",
                            "success",
                        );
                    }
                },
            });
        } catch (error) {
            updateStatus(
                statusElement,
                error instanceof Error ? error.message : "DOOM failed to start.",
                "danger",
            );
        }
    });
})();
