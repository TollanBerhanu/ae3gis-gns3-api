"""Pydantic models representing topology CRUD payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TopologyBase(BaseModel):
    """Fields shared by create/detail representations."""

    name: str = Field(..., min_length=1, description="User friendly name for the topology.")
    description: str | None = Field(default=None, description="Optional description for the topology.")
    scenario: dict[str, Any] = Field(
        ..., description="Scenario definition matching the scenario builder schema."
    )


class TopologyCreateRequest(TopologyBase):
    """Request body for creating a topology."""


class TopologyUpdateRequest(BaseModel):
    """Request body for updating a topology."""

    name: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None)
    scenario: dict[str, Any] | None = Field(default=None)

    def to_update_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.name is not None:
            payload["name"] = self.name
        if self.description is not None:
            payload["description"] = self.description
        if self.scenario is not None:
            payload["scenario"] = self.scenario
        return payload


class TopologySummary(BaseModel):
    """Lightweight representation for list responses."""

    id: str
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class TopologyDetail(TopologyBase):
    """Full topology record returned to clients."""

    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
