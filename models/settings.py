"""Application-wide configuration settings for the FastAPI service."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """Configuration options for the API layer."""

    config_path: Path = Field(Path("./config/config.generated.json"), description="Path to the generated config JSON file.")
    scripts_dir: Path = Field(Path("scripts"), description="Base directory containing pushable scripts.")
    gns3_request_delay: float = Field(0.0, ge=0.0, description="Optional delay between GNS3 API requests.")

    class Config:
        env_prefix = "GNS3_API_"
        case_sensitive = False
