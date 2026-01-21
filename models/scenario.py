"""Pydantic models related to scenario building operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class NodeDefaultScript(BaseModel):
    """Reference to a script that runs by default when a node is deployed."""

    script_id: str = Field(..., description="ID of the stored script.")
    remote_path: str = Field(default="/tmp/script.sh", description="Destination path on the node.")
    priority: int = Field(
        default=10,
        ge=1,
        description="Execution priority. Lower values run first (e.g., DHCP server=1, clients=10)."
    )
    shell: str = Field(default="sh", description="Shell used to execute the script.")
    timeout: float = Field(default=10.0, ge=0.0, description="Execution timeout in seconds.")


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
    run_default_scripts: bool = Field(
        default=False, 
        description="Execute default_scripts defined in nodes after starting them."
    )
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
    scripts_executed: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Results of default script executions, if run_default_scripts was true."
    )


class ScenarioBuildError(BaseModel):
    detail: str
