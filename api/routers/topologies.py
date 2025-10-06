"""Routes for managing reusable topology definitions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from core.topology_store import TopologyNotFoundError, TopologyRepository
from models import (
    TopologyCreateRequest,
    TopologyDetail,
    TopologySummary,
    TopologyUpdateRequest,
)

from ..dependencies import get_topology_repository

router = APIRouter(prefix="/topologies", tags=["topologies"])


@router.post("/", response_model=TopologyDetail, status_code=status.HTTP_201_CREATED)
def create_topology(
    payload: TopologyCreateRequest,
    repository: TopologyRepository = Depends(get_topology_repository),
) -> TopologyDetail:
    record = repository.create(payload.model_dump())
    return TopologyDetail.model_validate(record)


@router.get("/", response_model=list[TopologySummary])
def list_topologies(
    repository: TopologyRepository = Depends(get_topology_repository),
) -> list[TopologySummary]:
    records = repository.list_all()
    return [TopologySummary.model_validate(record) for record in records]


@router.get("/{topology_id}", response_model=TopologyDetail)
def get_topology(
    topology_id: str,
    repository: TopologyRepository = Depends(get_topology_repository),
) -> TopologyDetail:
    try:
        record = repository.get(topology_id)
    except TopologyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Topology not found") from exc
    return TopologyDetail.model_validate(record)


@router.patch("/{topology_id}", response_model=TopologyDetail)
def update_topology(
    topology_id: str,
    payload: TopologyUpdateRequest,
    repository: TopologyRepository = Depends(get_topology_repository),
) -> TopologyDetail:
    updates = payload.to_update_dict()
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    try:
        record = repository.update(topology_id, updates)
    except TopologyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Topology not found") from exc
    return TopologyDetail.model_validate(record)


@router.delete("/{topology_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topology(
    topology_id: str,
    repository: TopologyRepository = Depends(get_topology_repository),
) -> Response:
    try:
        repository.delete(topology_id)
    except TopologyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Topology not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
