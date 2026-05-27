from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from logger import Logger

from .config import STATIC_DIR, TEMPLATES_DIR
from .routes import router
from .state import PlaceholderStore


logger = Logger("DashboardApp")


def create_app() -> FastAPI:
    """Build and configure the FastAPI dashboard application.

    The application mounts local static assets, configures the Jinja template
    loader, initializes the shared placeholder state store, and registers the
    dashboard routes.

    Returns:
        FastAPI: A fully configured ASGI application ready to be served by
        uvicorn.
    """
    app = FastAPI(
        title="M2614 Dashboard",
        description="Placeholder monitoring and control dashboard for the M2614 robot.",
    )

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.state.templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.store = PlaceholderStore()
    app.include_router(router)

    logger.info("Dashboard app initialized")
    return app
