"""Utilities for caching and loading GNS3 template metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import requests

from .config_store import ConfigStore
from .gns3_client import GNS3Client


class TemplateCacheError(RuntimeError):
    """Raised when template caching or loading fails."""


def refresh_templates_cache(
    *,
    base_url: str,
    cache_path: Path,
    username: str | None = None,
    password: str | None = None,
    server_ip: str | None = None,
    server_port: int | None = None,
) -> dict[str, str]:
    """Fetch templates and projects from GNS3 and persist them."""

    base_url = base_url.rstrip("/")
    if not base_url:
        raise TemplateCacheError("A non-empty GNS3 base URL is required to refresh templates.")

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    if username and password:
        session.auth = (username, password)

    client = GNS3Client(base_url=base_url, session=session)

    try:
        template_map: dict[str, str] = {}
        for template in client.list_templates():
            name = template.get("name")
            template_id = template.get("template_id")
            if isinstance(name, str) and isinstance(template_id, str):
                template_map[name] = template_id

        project_map: dict[str, str] = {}
        for project in client.list_projects():
            name = project.get("name")
            project_id = project.get("project_id")
            if isinstance(name, str) and isinstance(project_id, str):
                project_map[name] = project_id
    finally:
        session.close()

    if not template_map:
        raise TemplateCacheError("No templates were returned by the GNS3 server.")

    payload = {
        "source": base_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "templates": template_map,
        "projects": project_map,
        "server": {
            "base_url": base_url,
            "ip": server_ip,
            "port": server_port,
        },
    }

    store = ConfigStore.from_path(cache_path)
    store.write(payload)

    return template_map


def load_registry(cache_path: Path | str) -> dict[str, Any]:
    """Return the raw registry payload from disk."""

    store = ConfigStore.from_path(cache_path)

    try:
        data = store.load()
    except FileNotFoundError as exc:
        raise TemplateCacheError(
            f"Template cache not found at {cache_path!s}. Start the API to generate it."
        ) from exc

    if not isinstance(data, Mapping):
        raise TemplateCacheError(
            f"Template cache at {cache_path!s} is malformed: expected a JSON object."
        )

    return dict(data)


def load_templates(cache_path: Path | str) -> dict[str, str]:
    """Load the cached name -> id map from disk."""

    registry = load_registry(cache_path)

    templates = registry.get("templates")
    if not isinstance(templates, Mapping):
        raise TemplateCacheError(
            f"Template cache at {cache_path!s} is malformed: missing 'templates' mapping."
        )

    return {str(name): str(template_id) for name, template_id in templates.items()}
