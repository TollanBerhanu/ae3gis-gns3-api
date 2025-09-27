"""Pydantic models related to scenario building operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ScenarioBuildRequest(BaseModel):
    """Request payload for building a scenario via the API."""

    scenario: dict[str, Any] = Field(..., description="Scenario definition matching the template JSON schema.")
    base_url: str | None = Field(
        default=None,
        description="Override for the GNS3 server base URL. Falls back to scenario['gns3_server_ip'].",
    )
    username: str | None = Field(default=None, description="Optional HTTP basic auth username for GNS3.")
    password: str | None = Field(default=None, description="Optional HTTP basic auth password for GNS3.")
    start_nodes: bool = Field(default=False, description="Start nodes immediately after creation.")
    config_path: Path | None = Field(
        default=None,
        description="Optional override for where to write the generated config JSON file.",
    )


class ScenarioBuildResponse(BaseModel):
    project_id: str
    project_name: str | None
    nodes_created: list[dict[str, Any]]
    links_created: list[dict[str, Any]]
    config_path: Path


class ScenarioBuildError(BaseModel):
    detail: str
