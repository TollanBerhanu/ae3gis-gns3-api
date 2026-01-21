"""Routes for building GNS3 scenarios."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException

from core.config_store import ConfigStore
from core.gns3_client import GNS3Client
from core.nodes import find_node_by_name, resolve_console_target
from core.scenario_builder import ScenarioBuilder
from core.script_pusher import ScriptPusher, ScriptSpec
from core.script_store import ScriptNotFoundError, ScriptRepository
from models import APISettings, ScenarioBuildRequest, ScenarioBuildResponse

from ..dependencies import get_settings, get_script_pusher, get_script_repository

router = APIRouter(prefix="/scenario", tags=["scenario"])


def _resolve_base_url(scenario: dict[str, object], override: str | None) -> str:
    if override:
        return override.rstrip("/")
    ip = scenario.get("gns3_server_ip")
    if not isinstance(ip, str) or not ip:
        raise ValueError("Scenario missing 'gns3_server_ip' and no base_url override provided")
    base = ip if ip.startswith("http") else f"http://{ip}"
    return base.rstrip("/")


async def _execute_default_scripts(
    scenario: dict[str, Any],
    config_record: dict[str, Any],
    gns3_server_ip: str | None,
    pusher: ScriptPusher,
    script_repo: ScriptRepository,
) -> list[dict[str, Any]]:
    """
    Execute default_scripts for all nodes, ordered by priority.
    
    Collects all script references from nodes, sorts by priority (lower first),
    and executes them sequentially.
    """
    nodes_spec = scenario.get("nodes", []) or []
    
    # Collect all script tasks with priority
    script_tasks: list[tuple[int, str, dict[str, Any]]] = []
    
    for node_spec in nodes_spec:
        node_name = node_spec.get("name")
        if not node_name:
            continue
        
        default_scripts = node_spec.get("default_scripts", [])
        if not default_scripts:
            continue
        
        for script_ref in default_scripts:
            script_id = script_ref.get("script_id")
            if not script_id:
                continue
            
            priority = script_ref.get("priority", 10)
            script_tasks.append((priority, node_name, script_ref))
    
    if not script_tasks:
        return []
    
    # Sort by priority (lower runs first)
    script_tasks.sort(key=lambda x: x[0])
    
    results: list[dict[str, Any]] = []
    
    for priority, node_name, script_ref in script_tasks:
        script_id = script_ref["script_id"]
        remote_path = script_ref.get("remote_path", "/tmp/script.sh")
        shell = script_ref.get("shell", "sh")
        timeout = script_ref.get("timeout", 10.0)
        
        # Find node in config to get console info
        node = find_node_by_name(config_record, node_name)
        if node is None:
            results.append({
                "node_name": node_name,
                "script_id": script_id,
                "priority": priority,
                "success": False,
                "error": f"Node '{node_name}' not found in config",
            })
            continue
        
        target = resolve_console_target(node, gns3_server_ip)
        if target is None:
            results.append({
                "node_name": node_name,
                "script_id": script_id,
                "priority": priority,
                "success": False,
                "error": f"Node '{node_name}' does not expose a telnet console",
            })
            continue
        
        host, port = target
        
        # Fetch script content
        try:
            content = script_repo.get_content(script_id)
        except ScriptNotFoundError:
            results.append({
                "node_name": node_name,
                "script_id": script_id,
                "priority": priority,
                "success": False,
                "error": f"Script '{script_id}' not found",
            })
            continue
        
        # Push and execute
        spec = ScriptSpec(
            remote_path=remote_path,
            content=content,
            run_after_upload=True,
            executable=True,
            overwrite=True,
            run_timeout=timeout,
            shell=shell,
        )
        
        try:
            push_result = await pusher.push(node_name, host, port, spec)
            results.append({
                "node_name": node_name,
                "script_id": script_id,
                "priority": priority,
                "remote_path": remote_path,
                "success": push_result.upload.success and (
                    push_result.execution.success if push_result.execution else False
                ),
                "upload": asdict(push_result.upload),
                "execution": asdict(push_result.execution) if push_result.execution else None,
            })
        except Exception as exc:
            results.append({
                "node_name": node_name,
                "script_id": script_id,
                "priority": priority,
                "success": False,
                "error": str(exc),
            })
    
    return results


@router.post("/build", response_model=ScenarioBuildResponse)
async def build_scenario(
    payload: ScenarioBuildRequest,
    settings: APISettings = Depends(get_settings),
    pusher: ScriptPusher = Depends(get_script_pusher),
    script_repo: ScriptRepository = Depends(get_script_repository),
) -> ScenarioBuildResponse:
    scenario = dict(payload.scenario)
    base_url = _resolve_base_url(scenario, payload.base_url)
    gns3_server_ip = scenario.get("gns3_server_ip")

    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    if payload.username and payload.password:
        session.auth = (payload.username, payload.password)

    client = GNS3Client(base_url=base_url, session=session)
    builder = ScenarioBuilder(client, request_delay=settings.gns3_request_delay)

    try:
        result = await asyncio.to_thread(builder.build, scenario, start_nodes=payload.start_nodes)
    except (LookupError, ValueError, requests.HTTPError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()

    config_path = payload.config_path or settings.config_path
    store = ConfigStore.from_path(config_path)
    store.write(result.config_record)

    # Execute default scripts if requested
    scripts_executed: list[dict[str, Any]] = []
    if payload.run_default_scripts and payload.start_nodes:
        # Small delay to allow nodes to fully start
        await asyncio.sleep(2.0)
        scripts_executed = await _execute_default_scripts(
            scenario=scenario,
            config_record=result.config_record,
            gns3_server_ip=gns3_server_ip,
            pusher=pusher,
            script_repo=script_repo,
        )

    return ScenarioBuildResponse(
        project_id=result.project_id,
        project_name=result.project_name,
        nodes_created=[dict(node) for node in result.nodes_created],
        links_created=[dict(link) for link in result.links_created],
        config_path=Path(config_path),
        scripts_executed=scripts_executed,
    )
