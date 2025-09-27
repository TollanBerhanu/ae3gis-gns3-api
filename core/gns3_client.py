"""Thin client for interacting with the GNS3 REST API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, MutableMapping

import requests


@dataclass(slots=True)
class GNS3Client:
    """Wrap an HTTP session with helpers for common GNS3 operations."""

    base_url: str
    session: requests.Session

    def get(self, path: str) -> Any:
        response = self.session.get(self._url(path))
        response.raise_for_status()
        return response.json()

    def post(self, path: str, *, json: Mapping[str, Any] | None = None) -> Any:
        response = self.session.post(self._url(path), json=json or {})
        response.raise_for_status()
        if response.text:
            try:
                return response.json()
            except ValueError:
                return response.text
        return {}

    def list_projects(self) -> list[MutableMapping[str, Any]]:
        return list(self.get("/v2/projects"))

    def find_project_id(self, project_name: str) -> str:
        for project in self.list_projects():
            if project.get("name") == project_name:
                return project["project_id"]
        raise LookupError(f"Project named '{project_name}' not found")

    def add_node_from_template(
        self,
        project_id: str,
        template_id: str,
        name: str,
        x: int,
        y: int,
    ) -> MutableMapping[str, Any]:
        payload = {"x": x, "y": y, "name": name}
        node = self.post(f"/v2/projects/{project_id}/templates/{template_id}", json=payload)
        if not isinstance(node, Mapping) or "node_id" not in node:
            raise RuntimeError(f"Failed to create node '{name}': {node}")
        return dict(node)

    def get_node(self, project_id: str, node_id: str) -> MutableMapping[str, Any]:
        node = self.get(f"/v2/projects/{project_id}/nodes/{node_id}")
        return dict(node)

    def create_link(
        self,
        project_id: str,
        node_a: Mapping[str, Any],
        node_b: Mapping[str, Any],
    ) -> MutableMapping[str, Any]:
        payload = {"nodes": [dict(node_a), dict(node_b)]}
        link = self.post(f"/v2/projects/{project_id}/links", json=payload)
        return dict(link)

    def start_node(self, project_id: str, node_id: str) -> bool:
        try:
            self.post(f"/v2/projects/{project_id}/nodes/{node_id}/start")
            return True
        except requests.HTTPError:
            return False

    def list_project_links(self, project_id: str) -> list[MutableMapping[str, Any]]:
        links = self.get(f"/v2/projects/{project_id}/links")
        return list(links)

    def list_templates(self) -> Iterable[MutableMapping[str, Any]]:
        templates = self.get("/v2/templates")
        for template in templates:
            yield dict(template)

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.base_url}{path}"
