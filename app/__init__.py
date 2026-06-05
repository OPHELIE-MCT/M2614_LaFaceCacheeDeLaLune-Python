from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from logger import Logger

from .config import STATIC_DIR, TEMPLATES_DIR
from .routes import router
from .state import CaptureStore


logger = Logger("DashboardApp")


def create_app() -> FastAPI:
    """Build and configure the FastAPI color-data-gather application."""
    app = FastAPI(
        title="M2614 Color Data Gather",
        description="Bridge-backed capture app for AS7341 calibration samples.",
    )

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.state.templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.store = CaptureStore()
    app.include_router(router)

    logger.info("Color data gather app initialized")
    return app
