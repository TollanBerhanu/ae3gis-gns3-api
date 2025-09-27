"""Application factory for the FastAPI service."""

from fastapi import FastAPI

from .dependencies import get_settings
from .routers import dhcp as dhcp_router
from .routers import scenario as scenario_router
from .routers import scripts as scripts_router
from models import APISettings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = APISettings()

    app = FastAPI(title="GNS3 Scenario Service", version="0.1.0")
    app.state.settings = settings
    app.dependency_overrides[get_settings] = lambda: settings

    app.include_router(scenario_router.router)
    app.include_router(dhcp_router.router)
    app.include_router(scripts_router.router)

    @app.get("/health", tags=["meta"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
