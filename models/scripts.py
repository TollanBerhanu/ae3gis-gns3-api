"""Pydantic models for script push-and-run operations."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class ScriptPushItem(BaseModel):
    node_name: str
    local_path: Path
    remote_path: str
    run_after_upload: bool = False
    executable: bool = True
    overwrite: bool = True
    run_timeout: float = Field(default=10.0, ge=0.0)
    shell: str = Field(default="sh", description="Shell used when executing the script after upload.")


class ScriptPushRequest(BaseModel):
    scripts: list[ScriptPushItem]
    gns3_server_ip: str | None = None
    concurrency: int = Field(default=5, ge=1, description="Maximum concurrent uploads.")


class ScriptUploadModel(BaseModel):
    node_name: str
    host: str
    port: int
    remote_path: str
    success: bool
    skipped: bool
    reason: str | None
    output: str
    error: str | None
    timestamp: float


class ScriptExecutionModel(BaseModel):
    node_name: str
    host: str
    port: int
    remote_path: str
    success: bool
    exit_code: int | None
    output: str
    error: str | None
    timestamp: float


class ScriptPushResultModel(BaseModel):
    upload: ScriptUploadModel
    execution: ScriptExecutionModel | None


class ScriptPushResponse(BaseModel):
    results: list[ScriptPushResultModel]


class ScriptRunItem(BaseModel):
    node_name: str
    remote_path: str
    shell: str = Field(default="sh", description="Shell used to execute the script.")
    timeout: float = Field(default=10.0, ge=0.0)


class ScriptRunRequest(BaseModel):
    runs: list[ScriptRunItem]
    gns3_server_ip: str | None = None
    concurrency: int = Field(default=5, ge=1)


class ScriptRunResponse(BaseModel):
    results: list[ScriptExecutionModel]
