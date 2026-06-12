# M2614 La Face Cachee De La Lune Python

Python application repository for the Uno Q SBC side of the M2614 project.

## What lives here

- the FastAPI web app used on the `ball-data-gather` branch to control color-sensor capture sessions
- the local RouterBridge client implementation in `bridge.py`
- the CSV capture flow that stores labeled AS7341 samples for later analysis in `ball-analyzer`

## Run locally

```powershell
uv sync
uv run main.py
```

The app listens on `0.0.0.0:8000` by default. The output CSV is written to `data/color_sensor_samples.csv`.

## Capture workflow

- choose the current ball color in the web UI
- start a capture session
- receive `color_sensor.sample` notifications from the Uno Q sketch through RouterBridge
- stop automatically after 100 saved samples

## All-in-one calibration workflow

- reset the local CSV from the web UI after a confirmation prompt
- download the current CSV directly from the Uno Q SBC
- run the centroid analysis locally on the Uno Q SBC without Jupyter
- save generated plots locally and expose clickable links in the UI
- display the paste-ready C++ centroid array and unknown threshold
- trigger `arduino-reset` from the UI when the MCU must be restarted

This repo is meant to be used together with the Arduino repo for capture and the `ball-analyzer` repo for recalculating classifier centroids.
