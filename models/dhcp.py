"""Pydantic models for DHCP assignment operations."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class NodeExecutionModel(BaseModel):
    name: str
    host: str
    port: int
    action: str
    success: bool
    output: str | None = None
    error: str | None = None
    assigned_ip: str | None = None


class DHCPAssignRequest(BaseModel):
    gns3_server_ip: str | None = Field(
        default=None,
        description="Override console host address for all nodes (e.g., 192.168.56.1).",
    )
    dhclient_timeout: float = Field(default=15.0, ge=1.0, description="Seconds to wait for dhclient output per node.")
    dhcp_warmup: float = Field(default=2.0, ge=0.0, description="Seconds to sleep after starting DHCP servers.")


class DHCPAssignResponse(BaseModel):
    changed: bool
    backup_path: Path | None
    server_results: list[NodeExecutionModel]
    client_results: list[NodeExecutionModel]
