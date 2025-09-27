"""Routes for DHCP assignment workflows."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends

from typing import Sequence

from core.dhcp_assigner import DHCPAssigner, NodeExecutionResult
from models import DHCPAssignRequest, DHCPAssignResponse, NodeExecutionModel

from ..dependencies import get_dhcp_assigner

router = APIRouter(prefix="/dhcp", tags=["dhcp"])


def _convert(results: Sequence[NodeExecutionResult]) -> list[NodeExecutionModel]:
    return [NodeExecutionModel(**asdict(item)) for item in results]


@router.post("/assign", response_model=DHCPAssignResponse)
async def assign_dhcp(
    payload: DHCPAssignRequest,
    assigner: DHCPAssigner = Depends(get_dhcp_assigner),
) -> DHCPAssignResponse:
    result = await assigner.assign(
        host_override=payload.host_override,
        dhclient_timeout=payload.dhclient_timeout,
        dhcp_warmup=payload.dhcp_warmup,
    )

    return DHCPAssignResponse(
        changed=result.changed,
        backup_path=result.backup_path,
        server_results=_convert(result.server_results),
        client_results=_convert(result.client_results),
    )
