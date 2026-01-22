"""Routes for managing and deploying scenarios."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any, MutableMapping

import requests
from fastapi import APIRouter, Depends, HTTPException, Response, status

from core.config_store import ConfigStore
from core.gns3_client import GNS3Client
from core.nodes import find_node_by_name, resolve_console_target
from core.scenario_builder import ScenarioBuilder
from core.scenario_store import ScenarioNotFoundError, ScenarioRepository
from core.script_pusher import ScriptPusher, ScriptSpec
from models.scenario_types import (
    ScenarioCreateRequest,
    ScenarioDefinition,
    ScenarioDeployRequest,
    ScenarioDeployResponse,
    ScenarioDetail,
    ScenarioSummary,
    ScenarioUpdateRequest,
    ScriptExecutionSummary,
)
from models import APISettings

from ..dependencies import get_scenario_repository, get_script_pusher, get_settings

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


# -----------------------------------------------------------------------------
# Scenario CRUD Endpoints
# -----------------------------------------------------------------------------


@router.post("/", response_model=ScenarioDetail, status_code=status.HTTP_201_CREATED)
def create_scenario(
    payload: ScenarioCreateRequest,
    repository: ScenarioRepository = Depends(get_scenario_repository),
) -> ScenarioDetail:
    """Create a new scenario (instructor use)."""
    data = {
        "name": payload.name,
        "description": payload.description,
        "definition": payload.definition.model_dump(),
    }
    record = repository.create(data)
    return ScenarioDetail.model_validate(record)


@router.get("/", response_model=list[ScenarioSummary])
def list_scenarios(
    repository: ScenarioRepository = Depends(get_scenario_repository),
) -> list[ScenarioSummary]:
    """List all stored scenarios."""
    records = repository.list_all()
    return [ScenarioSummary.model_validate(record) for record in records]


@router.get("/{scenario_id}", response_model=ScenarioDetail)
def get_scenario(
    scenario_id: str,
    repository: ScenarioRepository = Depends(get_scenario_repository),
) -> ScenarioDetail:
    """Retrieve a scenario by ID."""
    try:
        record = repository.get(scenario_id)
    except ScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Scenario not found") from exc
    return ScenarioDetail.model_validate(record)


@router.patch("/{scenario_id}", response_model=ScenarioDetail)
def update_scenario(
    scenario_id: str,
    payload: ScenarioUpdateRequest,
    repository: ScenarioRepository = Depends(get_scenario_repository),
) -> ScenarioDetail:
    """Update a scenario's metadata or definition (instructor use)."""
    updates = payload.to_update_dict()
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    try:
        record = repository.update(scenario_id, updates)
    except ScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Scenario not found") from exc
    return ScenarioDetail.model_validate(record)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: str,
    repository: ScenarioRepository = Depends(get_scenario_repository),
) -> Response:
    """Delete a scenario by ID (instructor use)."""
    try:
        repository.delete(scenario_id)
    except ScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Scenario not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -----------------------------------------------------------------------------
# Scenario Deployment Endpoint
# -----------------------------------------------------------------------------


async def _execute_embedded_scripts(
    definition: ScenarioDefinition,
    config_record: MutableMapping[str, Any],
    gns3_server_ip: str,
    pusher: ScriptPusher,
    priority_delay: float,
) -> list[ScriptExecutionSummary]:
    """
    Execute all embedded scripts from nodes in priority order.
    
    Scripts are sorted by priority (lower first). A delay is added
    between different priority groups to allow services to initialize.
    """
    # Collect all scripts with their node info
    script_tasks: list[tuple[int, str, Any]] = []
    
    for node in definition.nodes:
        for script in node.scripts:
            script_tasks.append((script.priority, node.name, script))
    
    if not script_tasks:
        return []
    
    # Sort by priority
    script_tasks.sort(key=lambda x: x[0])
    
    results: list[ScriptExecutionSummary] = []
    current_priority: int | None = None
    
    for priority, node_name, script in script_tasks:
        # Add delay when moving to a new priority group
        if current_priority is not None and priority > current_priority and priority_delay > 0:
            await asyncio.sleep(priority_delay)
        current_priority = priority
        
        # Find node in config to get console info
        node = find_node_by_name(config_record, node_name)
        if node is None:
            results.append(ScriptExecutionSummary(
                node_name=node_name,
                script_name=script.name,
                priority=priority,
                remote_path=script.remote_path,
                success=False,
                error=f"Node '{node_name}' not found in config",
            ))
            continue
        
        target = resolve_console_target(node, gns3_server_ip)
        if target is None:
            results.append(ScriptExecutionSummary(
                node_name=node_name,
                script_name=script.name,
                priority=priority,
                remote_path=script.remote_path,
                success=False,
                error=f"Node '{node_name}' does not expose a telnet console",
            ))
            continue
        
        host, port = target
        
        # Create spec with embedded content
        spec = ScriptSpec(
            remote_path=script.remote_path,
            content=script.content,
            run_after_upload=True,
            executable=True,
            overwrite=True,
            run_timeout=script.timeout,
            shell=script.shell,
        )
        
        try:
            push_result = await pusher.push(node_name, host, port, spec)
            success = push_result.upload.success and (
                push_result.execution.success if push_result.execution else False
            )
            error = None
            if not push_result.upload.success:
                error = push_result.upload.error or push_result.upload.reason
            elif push_result.execution and not push_result.execution.success:
                error = push_result.execution.error
            
            results.append(ScriptExecutionSummary(
                node_name=node_name,
                script_name=script.name,
                priority=priority,
                remote_path=script.remote_path,
                success=success,
                error=error,
            ))
        except Exception as exc:
            results.append(ScriptExecutionSummary(
                node_name=node_name,
                script_name=script.name,
                priority=priority,
                remote_path=script.remote_path,
                success=False,
                error=str(exc),
            ))
    
    return results


@router.post("/{scenario_id}/deploy", response_model=ScenarioDeployResponse)
async def deploy_scenario(
    scenario_id: str,
    payload: ScenarioDeployRequest,
    repository: ScenarioRepository = Depends(get_scenario_repository),
    pusher: ScriptPusher = Depends(get_script_pusher),
    settings: APISettings = Depends(get_settings),
) -> ScenarioDeployResponse:
    """
    Deploy a scenario to a student's GNS3 server.
    
    This endpoint:
    1. Loads the scenario definition
    2. Creates all nodes and links in the student's GNS3 project
    3. Starts all nodes
    4. Executes embedded scripts in priority order (with delays between groups)
    """
    # Load scenario
    try:
        record = repository.get(scenario_id)
    except ScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Scenario not found") from exc
    
    definition = ScenarioDefinition.model_validate(record["definition"])
    scenario_name = record["name"]
    
    # Build base URL from student's GNS3 server
    base_url = f"http://{payload.gns3_server_ip}:{payload.gns3_server_port}"
    
    # Prepare scenario dict for builder (convert to legacy format)
    project_name = payload.project_name or definition.project_name
    if not project_name and not definition.project_id:
        raise HTTPException(
            status_code=400, 
            detail="Either project_name must be provided or defined in scenario"
        )
    
    scenario_dict: dict[str, Any] = {
        "gns3_server_ip": payload.gns3_server_ip,
        "project_name": project_name,
        "project_id": definition.project_id,
        "templates": definition.templates,
        "nodes": [
            {
                "name": node.name,
                "template_id": node.template_id,
                "template_key": node.template_key,
                "template_name": node.template_name,
                "x": node.x,
                "y": node.y,
            }
            for node in definition.nodes
        ],
        "links": [
            {
                "nodes": [
                    {
                        "node_id": link.nodes[0].name,
                        "adapter_number": link.nodes[0].adapter_number,
                        "port_number": link.nodes[0].port_number,
                    },
                    {
                        "node_id": link.nodes[1].name,
                        "adapter_number": link.nodes[1].adapter_number,
                        "port_number": link.nodes[1].port_number,
                    },
                ]
            }
            for link in definition.links
        ],
    }
    
    # Create GNS3 client and builder
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    session.auth = (payload.username, payload.password)
    
    client = GNS3Client(base_url=base_url, session=session)
    builder = ScenarioBuilder(client, request_delay=settings.gns3_request_delay)
    
    errors: list[str] = []
    
    try:
        # Build scenario (create nodes and links)
        result = await asyncio.to_thread(
            builder.build, 
            scenario_dict, 
            start_nodes=payload.start_nodes
        )
    except (LookupError, ValueError, requests.HTTPError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()
    
    # Write config for script execution
    store = ConfigStore.from_path(settings.config_path)
    store.write(result.config_record)
    
    # Execute scripts if requested
    scripts_executed: list[ScriptExecutionSummary] = []
    if payload.run_scripts and payload.start_nodes:
        # Initial delay for nodes to boot
        await asyncio.sleep(2.0)
        
        scripts_executed = await _execute_embedded_scripts(
            definition=definition,
            config_record=result.config_record,
            gns3_server_ip=payload.gns3_server_ip,
            pusher=pusher,
            priority_delay=payload.priority_delay,
        )
        
        # Collect errors from failed scripts
        for exec_result in scripts_executed:
            if not exec_result.success and exec_result.error:
                errors.append(f"{exec_result.node_name}/{exec_result.script_name}: {exec_result.error}")
    
    overall_success = len(errors) == 0 and len(result.nodes_created) > 0
    
    return ScenarioDeployResponse(
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        project_id=result.project_id,
        project_name=result.project_name,
        gns3_server_ip=payload.gns3_server_ip,
        nodes_created=len(result.nodes_created),
        links_created=len(result.links_created),
        scripts_executed=scripts_executed,
        success=overall_success,
        errors=errors,
    )
