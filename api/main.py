"""Application factory for the FastAPI service."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from .dependencies import get_settings
from .routers import dhcp as dhcp_router
from .routers import scenarios as scenarios_router
from .routers import scripts as scripts_router
from models import APISettings


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = APISettings()  # type: ignore[call-arg]

    app = FastAPI(title="GNS3 Scenario Service", version="0.2.0")
    app.state.settings = settings
    app.dependency_overrides[get_settings] = lambda: settings

    app.include_router(scenarios_router.router)
    app.include_router(dhcp_router.router)
    app.include_router(scripts_router.router)

    # No startup dependency on GNS3 - all connection details come from frontend

    @app.get("/health", tags=["meta"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
