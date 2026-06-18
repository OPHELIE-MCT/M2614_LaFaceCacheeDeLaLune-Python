from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

router = APIRouter()


class GatherStartRequest(BaseModel):
    """Payload used to start a labeled data gathering session."""

    color: str


@router.get("/", response_class=HTMLResponse)
async def gather_page(request: Request) -> HTMLResponse:
    status_payload = request.app.state.store.status_payload()
    context: dict[str, object] = {
        "request": request,
        "page_title": "Color Data Gather",
        "status": status_payload,
    }
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="gather.html",
        context=context,
    )


@router.get("/doom", response_class=HTMLResponse)
async def doom_page(request: Request) -> HTMLResponse:
    context: dict[str, object] = {
        "request": request,
        "page_title":  "DOOM sur l'Arduino UNO Q",
        "doom_bundle_static_path": "vendor/doom/doom-shareware.jsdos",
    }
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="doom.html",
        context=context,
    )


@router.get("/minecraft", response_class=HTMLResponse)
async def minecraft_page(request: Request) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="minecraft.html",
        context={},
    )


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    return request.app.state.store.health_payload()


@router.get("/api/gather/status")
async def gather_status_api(request: Request) -> dict[str, object]:
    return request.app.state.store.poll_status()


@router.post("/api/gather/start")
async def start_gather_api(
    request: Request, payload: GatherStartRequest
) -> dict[str, object]:
    try:
        status_payload = request.app.state.store.start_gathering(payload.color)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return {"message": status_payload["status_message"], "status": status_payload}


@router.post("/api/gather/stop")
async def stop_gather_api(request: Request) -> dict[str, object]:
    try:
        status_payload = request.app.state.store.stop_gathering()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return {"message": status_payload["status_message"], "status": status_payload}


@router.post("/api/gather/csv/reset")
async def reset_csv_api(request: Request) -> dict[str, object]:
    try:
        status_payload = request.app.state.store.reset_csv()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"message": status_payload["status_message"], "status": status_payload}


@router.get("/api/gather/csv/download")
async def download_csv_api(request: Request) -> FileResponse:
    try:
        csv_path = request.app.state.store.csv_file_path()
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return FileResponse(path=csv_path, filename=csv_path.name, media_type="text/csv")


@router.post("/api/gather/analysis/run")
async def run_analysis_api(request: Request) -> dict[str, object]:
    try:
        status_payload = request.app.state.store.run_analysis()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return {"message": status_payload["analysis_message"], "status": status_payload}


@router.get("/api/gather/analysis/download-config-header")
async def download_config_header_api(request: Request) -> Response:
    status_payload = request.app.state.store.status_payload()
    cpp_code = str(status_payload.get("analysis_cpp_code") or "").strip()
    if not cpp_code:
        raise HTTPException(
            status_code=404,
            detail="No generated config.h is available yet. Run centroid analysis first.",
        )

    header_content = cpp_code if cpp_code.endswith("\n") else cpp_code + "\n"
    return Response(
        content=header_content,
        media_type="text/x-c++hdr; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=config.h"},
    )


@router.post("/api/gather/device/reset")
async def reset_device_api(request: Request) -> dict[str, object]:
    try:
        status_payload = request.app.state.store.reset_arduino()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return {"message": status_payload["status_message"], "status": status_payload}


class AutonomousModeRequest(BaseModel):
    """Payload used to enable or disable the robot autonomous fallback."""

    enabled: bool


@router.post("/api/robot/autonomous")
async def set_autonomous_mode_api(
    request: Request, payload: AutonomousModeRequest
) -> dict[str, object]:
    try:
        status_payload = request.app.state.store.set_autonomous_mode(
            payload.enabled)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return {
        "message": (
            "Autonomous mode enabled." if payload.enabled else "Autonomous mode disabled."
        ),
        "status": status_payload,
    }
