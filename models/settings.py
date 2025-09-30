"""Application-wide configuration settings for the FastAPI service."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """Configuration options for the API layer."""

    config_path: Path = Field(Path("./config/config.generated.json"), description="Path to the generated config JSON file.")
    scripts_dir: Path = Field(Path("scripts"), description="Base directory containing pushable scripts.")
    gns3_request_delay: float = Field(0.0, ge=0.0, description="Optional delay between GNS3 API requests.")
    gns3_base_url_override: str | None = Field(
        default_factory=lambda: os.getenv("GNS3_BASE_URL") or os.getenv("GNS3_API_BASE_URL"),
        description="Optional explicit base URL for the GNS3 REST API.",
    )
    gns3_server_ip: str = Field(
        default_factory=lambda: os.getenv("GNS3_SERVER_IP") or "172.16.194.129",
        description="IP address or hostname of the GNS3 server.",
    )
    gns3_server_port: int = Field(
        default_factory=lambda: int(os.getenv("GNS3_SERVER_PORT") or 80),
        description="HTTP port exposed by the GNS3 REST API.",
    )
    gns3_username: str | None = Field(
        default_factory=lambda: os.getenv("GNS3_SERVER_USER") or os.getenv("GNS3_API_GNS3_USERNAME"),
        description="Optional username for authenticating with the GNS3 REST API.",
    )
    gns3_password: str | None = Field(
        default_factory=lambda: os.getenv("GNS3_SERVER_PASSWORD") or os.getenv("GNS3_API_GNS3_PASSWORD"),
        description="Optional password for authenticating with the GNS3 REST API.",
    )
    templates_cache_path: Path = Field(
        Path("./config/templates.generated.json"),
        description="Location where the template name/id cache will be written.",
    )

    @computed_field
    @property
    def gns3_base_url(self) -> str:
        base = (self.gns3_base_url_override or "").rstrip("/")
        if base:
            return base
        return f"http://{self.gns3_server_ip}:{self.gns3_server_port}"

    class Config:
        env_prefix = "GNS3_API_"
        case_sensitive = False
