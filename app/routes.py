from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
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


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    return request.app.state.store.health_payload()


@router.get("/api/gather/status")
async def gather_status_api(request: Request) -> dict[str, object]:
    return request.app.state.store.status_payload()


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
