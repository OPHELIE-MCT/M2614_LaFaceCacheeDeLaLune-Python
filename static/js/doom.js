(function () {
    function updateStatus(statusElement, message, tone) {
        if (!statusElement) {
            return;
        }

        statusElement.textContent = message;
        statusElement.dataset.tone = tone;
    }

    const wasdArrowMap = {
        KeyW: { key: "ArrowUp", code: "ArrowUp", keyCode: 38 },
        KeyA: { key: "ArrowLeft", code: "ArrowLeft", keyCode: 37 },
        KeyS: { key: "ArrowDown", code: "ArrowDown", keyCode: 40 },
        KeyD: { key: "ArrowRight", code: "ArrowRight", keyCode: 39 },
    };

    function dispatchRemappedKey(originalEvent, mappedKey) {
        const remappedEvent = new KeyboardEvent(originalEvent.type, {
            key: mappedKey.key,
            code: mappedKey.code,
            bubbles: true,
            cancelable: true,
            composed: true,
            ctrlKey: originalEvent.ctrlKey,
            shiftKey: originalEvent.shiftKey,
            altKey: originalEvent.altKey,
            metaKey: originalEvent.metaKey,
            repeat: originalEvent.repeat,
            location: originalEvent.location,
        });

        Object.defineProperties(remappedEvent, {
            keyCode: { value: mappedKey.keyCode, configurable: true },
            which: { value: mappedKey.keyCode, configurable: true },
        });

        window.dispatchEvent(remappedEvent);
    }

    function shouldIgnoreKeyEvent(event) {
        const target = event.target;
        const tagName = target && target.tagName ? target.tagName.toLowerCase() : "";

        return (
            event.altKey ||
            event.metaKey ||
            tagName === "input" ||
            tagName === "textarea" ||
            tagName === "select" ||
            Boolean(target && target.isContentEditable)
        );
    }

    function installWasdControls() {
        window.addEventListener(
            "keydown",
            function (event) {
                const mappedKey = wasdArrowMap[event.code];
                if (!mappedKey || shouldIgnoreKeyEvent(event)) {
                    return;
                }

                event.preventDefault();
                event.stopImmediatePropagation();
                dispatchRemappedKey(event, mappedKey);
            },
            true,
        );

        window.addEventListener(
            "keyup",
            function (event) {
                const mappedKey = wasdArrowMap[event.code];
                if (!mappedKey || shouldIgnoreKeyEvent(event)) {
                    return;
                }

                event.preventDefault();
                event.stopImmediatePropagation();
                dispatchRemappedKey(event, mappedKey);
            },
            true,
        );
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
            updateStatus(statusElement, "Le moteur js-dos n'a pas pu se charger.", "danger");
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

        updateStatus(statusElement, "Démarrage de la version shareware de DOOM...", "loading");
        installWasdControls();

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
                            "DOOM est prêt. Cliquez sur le jeu pour capturer les commandes.",
                            "success",
                        );
                    }
                },
            });
        } catch (error) {
            updateStatus(
                statusElement,
                error instanceof Error ? error.message : "Échec du démarrage de DOOM.",
                "danger",
            );
        }
    });
})();
