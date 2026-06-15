from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from .config import DOOM_BUNDLE_STATIC_PATH, DOOM_PAGE_PATH, DOOM_PAGE_TITLE


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


@router.get(DOOM_PAGE_PATH, response_class=HTMLResponse)
async def doom_page(request: Request) -> HTMLResponse:
    context: dict[str, object] = {
        "request": request,
        "page_title": DOOM_PAGE_TITLE,
        "doom_bundle_static_path": DOOM_BUNDLE_STATIC_PATH,
    }
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="doom.html",
        context=context,
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


@router.post("/api/gather/device/reset")
async def reset_device_api(request: Request) -> dict[str, object]:
    try:
        status_payload = request.app.state.store.reset_arduino()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return {"message": status_payload["status_message"], "status": status_payload}
