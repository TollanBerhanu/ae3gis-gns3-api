"""Routes for uploading and running scripts on topology nodes."""

from __future__ import annotations

import asyncio
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from core.config_store import ConfigStore
from core.nodes import find_node_by_name, resolve_console_target
from core.script_pusher import ScriptExecutionResult, ScriptPusher, ScriptSpec, ScriptTask
from models import (
    ScriptExecutionModel,
    ScriptPushRequest,
    ScriptPushResponse,
    ScriptPushResultModel,
    ScriptRunRequest,
    ScriptRunResponse,
    ScriptUploadModel,
)

from ..dependencies import get_config_store, get_script_pusher

router = APIRouter(prefix="/scripts", tags=["scripts"])


def _ensure_node(config: dict, node_name: str):
    node = find_node_by_name(config, node_name)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found in config")
    return node


def _ensure_console(node: dict, node_name: str, gns3_server_ip: str | None) -> tuple[str, int]:
    target = resolve_console_target(node, gns3_server_ip)
    if target is None:
        raise HTTPException(status_code=400, detail=f"Node '{node_name}' does not expose a telnet console")
    return target


@router.post("/push", response_model=ScriptPushResponse)
async def push_scripts(
    payload: ScriptPushRequest,
    config_store: ConfigStore = Depends(get_config_store),
    pusher: ScriptPusher = Depends(get_script_pusher),
) -> ScriptPushResponse:
    if not payload.scripts:
        raise HTTPException(status_code=400, detail="No scripts provided")

    config = config_store.load()

    tasks: list[ScriptTask] = []
    for item in payload.scripts:
        node = _ensure_node(config, item.node_name)
        host, port = _ensure_console(node, item.node_name, payload.gns3_server_ip)
        try:
            spec = ScriptSpec(
                local_path=item.local_path,
                remote_path=item.remote_path,
                run_after_upload=item.run_after_upload,
                executable=item.executable,
                overwrite=item.overwrite,
                run_timeout=item.run_timeout,
                shell=item.shell,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        tasks.append(ScriptTask(node_name=item.node_name, host=host, port=port, spec=spec))

    results = await pusher.push_many(tasks, concurrency=payload.concurrency)

    response_items = [
        ScriptPushResultModel(
            upload=ScriptUploadModel(**asdict(result.upload)),
            execution=ScriptExecutionModel(**asdict(result.execution)) if result.execution else None,
        )
        for result in results
    ]
    return ScriptPushResponse(results=response_items)


async def _run_single(
    item,
    config: dict,
    gns3_server_ip: str | None,
    pusher: ScriptPusher,
    semaphore: asyncio.Semaphore,
) -> ScriptExecutionResult:
    node = _ensure_node(config, item.node_name)
    host, port = _ensure_console(node, item.node_name, gns3_server_ip)
    async with semaphore:
        return await pusher.run(
            item.node_name,
            host,
            port,
            item.remote_path,
            shell=item.shell,
            timeout=item.timeout,
        )


@router.post("/run", response_model=ScriptRunResponse)
async def run_scripts(
    payload: ScriptRunRequest,
    config_store: ConfigStore = Depends(get_config_store),
    pusher: ScriptPusher = Depends(get_script_pusher),
) -> ScriptRunResponse:
    if not payload.runs:
        raise HTTPException(status_code=400, detail="No run requests provided")

    config = config_store.load()
    semaphore = asyncio.Semaphore(max(1, payload.concurrency))
    results = await asyncio.gather(
        *(
            _run_single(item, config, payload.gns3_server_ip, pusher, semaphore)
            for item in payload.runs
        )
    )
    return ScriptRunResponse(results=[ScriptExecutionModel(**asdict(res)) for res in results])
