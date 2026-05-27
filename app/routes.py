from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel


router = APIRouter()


class ModeUpdate(BaseModel):
    """Payload used to request a robot mode change."""

    mode: str


class SortingUpdate(BaseModel):
    """Payload used to enable or disable the manual sorting override."""

    enabled: bool


@router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/monitoring", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/monitoring", response_class=HTMLResponse)
async def monitoring_page(request: Request) -> HTMLResponse:
    return _render_page(
        request=request,
        template_name="monitoring.html",
        page_title="Monitoring",
        active_page="monitoring",
    )


@router.get("/control", response_class=HTMLResponse)
async def control_page(request: Request) -> HTMLResponse:
    return _render_page(
        request=request,
        template_name="control.html",
        page_title="Control",
        active_page="control",
    )


@router.get("/api/dashboard", name="dashboard_api")
async def dashboard_api(request: Request) -> dict[str, object]:
    """Return the full placeholder dashboard payload.

    Args:
        request: Incoming FastAPI request whose app state contains the shared
        placeholder store.

    Returns:
        dict[str, object]: The current monitoring, control, and metadata payload
        consumed by the frontend.
    """
    return request.app.state.store.dashboard_payload()


@router.get("/api/system", name="system_api")
async def system_api(request: Request) -> dict[str, float]:
    """Return the current host CPU and RAM usage snapshot.

    Args:
        request: Incoming FastAPI request whose app state contains the shared
        placeholder store.

    Returns:
        dict[str, float]: CPU and memory usage percentages for the SBC host.
    """
    return request.app.state.store.system_metrics()


@router.get("/api/lidar/status", name="lidar_status_api")
async def lidar_status_api(request: Request) -> dict[str, object]:
    """Return the placeholder LiDAR panel status.

    Args:
        request: Incoming FastAPI request whose app state contains the shared
        placeholder store.

    Returns:
        dict[str, object]: Placeholder LiDAR metadata for the monitoring page.
    """
    return request.app.state.store.lidar_status()


@router.get("/api/modes", name="modes_api")
async def modes_api(request: Request) -> list[dict[str, object]]:
    """Return the available robot modes for the control page.

    Args:
        request: Incoming FastAPI request whose app state contains the shared
        placeholder store.

    Returns:
        list[dict[str, object]]: The list of configured modes with their active
        status.
    """
    return request.app.state.store.modes_payload()


@router.post("/api/control/mode", name="set_mode_api")
async def set_mode_api(
    request: Request, payload: ModeUpdate
) -> dict[str, object]:
    """Update the placeholder robot mode.

    Args:
        request: Incoming FastAPI request whose app state contains the shared
        placeholder store.
        payload: Requested robot mode selection.

    Returns:
        dict[str, object]: A message describing the action and the refreshed
        dashboard payload.

    Raises:
        HTTPException: Raised with status 400 when the requested mode key is not
        valid.
    """
    try:
        dashboard = request.app.state.store.set_mode(payload.mode)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"message": dashboard["meta"]["last_action"], "dashboard": dashboard}


@router.post("/api/control/sorting", name="set_sorting_api")
async def set_sorting_api(
    request: Request, payload: SortingUpdate
) -> dict[str, object]:
    """Toggle the manual sorting override in the placeholder store.

    Args:
        request: Incoming FastAPI request whose app state contains the shared
        placeholder store.
        payload: Requested enabled state for the sorting override.

    Returns:
        dict[str, object]: A message describing the action and the refreshed
        dashboard payload.

    Raises:
        HTTPException: Raised with status 400 when the requested state conflicts
        with safety rules such as emergency mode.
    """
    try:
        dashboard = request.app.state.store.set_sorting_enabled(
            payload.enabled)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"message": dashboard["meta"]["last_action"], "dashboard": dashboard}


@router.post("/api/control/calibrations/{calibration_key}", name="run_calibration_api")
async def run_calibration_api(
    request: Request, calibration_key: str
) -> dict[str, object]:
    """Queue a placeholder calibration action.

    Args:
        request: Incoming FastAPI request whose app state contains the shared
        placeholder store.
        calibration_key: Identifier of the calibration sequence to queue.

    Returns:
        dict[str, object]: A message describing the action and the refreshed
        dashboard payload.

    Raises:
        HTTPException: Raised with status 400 when the requested calibration key
        is unknown.
    """
    try:
        dashboard = request.app.state.store.run_calibration(calibration_key)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"message": dashboard["meta"]["last_action"], "dashboard": dashboard}


def _render_page(
    *,
    request: Request,
    template_name: str,
    page_title: str,
    active_page: str,
) -> HTMLResponse:
    dashboard = request.app.state.store.dashboard_payload()
    context: dict[str, object] = {
        "request": request,
        "page_title": page_title,
        "active_page": active_page,
        "dashboard": dashboard,
    }
    return request.app.state.templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
    )
