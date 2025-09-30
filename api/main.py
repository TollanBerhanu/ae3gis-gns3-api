"""Application factory for the FastAPI service."""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI

from .dependencies import get_settings
from .routers import dhcp as dhcp_router
from .routers import scenario as scenario_router
from .routers import scripts as scripts_router
from core.template_cache import TemplateCacheError, refresh_templates_cache
from models import APISettings


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = APISettings()  # type: ignore[call-arg]

    app = FastAPI(title="GNS3 Scenario Service", version="0.1.0")
    app.state.settings = settings
    app.dependency_overrides[get_settings] = lambda: settings

    app.include_router(scenario_router.router)
    app.include_router(dhcp_router.router)
    app.include_router(scripts_router.router)

    @app.on_event("startup")
    async def warm_template_cache() -> None:
        def _refresh() -> None:
            refresh_templates_cache(
                base_url=settings.gns3_base_url,
                cache_path=settings.templates_cache_path,
                username=settings.gns3_username,
                password=settings.gns3_password,
                server_ip=settings.gns3_server_ip,
                server_port=settings.gns3_server_port,
            )

        try:
            await asyncio.to_thread(_refresh)
        except TemplateCacheError as exc:
            logger.exception("Failed to refresh GNS3 template cache: %s", exc)
            raise

    @app.get("/health", tags=["meta"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
