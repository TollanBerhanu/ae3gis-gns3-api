"""Utilities for working with node records in the generated config."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Sequence
from urllib.parse import urlparse


def _normalize_host(value: Any) -> str | None:
    if value is None:
        return None
    host = str(value).strip()
    if not host:
        return None

    parsed = urlparse(host)
    candidate = parsed.hostname if parsed.hostname else None

    if candidate is None and parsed.scheme and parsed.netloc:
        candidate = parsed.netloc.split("@")[-1]

    if candidate is None:
        raw = host
        if "//" in raw:
            raw = raw.split("//", 1)[-1]
        raw = raw.split("/", 1)[0]
        if raw.startswith("[") and "]" in raw:
            candidate = raw[1 : raw.index("]")]
        else:
            candidate = raw.split(":", 1)[0]

    if not candidate:
        return None

    candidate = candidate.strip()
    if candidate in {"", "0.0.0.0"}:
        return None
    return candidate


def resolve_console_target(node: Mapping[str, Any], gns3_server_ip: str | None = None) -> tuple[str, int] | None:
    """Return the console host/port tuple for a node if available."""

    port = node.get("console")
    if port is None:
        return None
    try:
        port_int = int(port)
    except (TypeError, ValueError):
        return None

    for candidate in (gns3_server_ip, node.get("console_host"), "127.0.0.1"):
        normalized = _normalize_host(candidate)
        if normalized:
            return normalized, port_int

    return None


def iter_nodes(config: Mapping[str, Any]) -> Sequence[MutableMapping[str, Any]]:
    """Return the list of node records from a generated config."""

    nodes = config.get("nodes", [])
    if not isinstance(nodes, Sequence):
        return []
    return [node for node in nodes if isinstance(node, MutableMapping)]


def find_node_by_name(config: Mapping[str, Any], name: str) -> MutableMapping[str, Any] | None:
    """Locate a node record by name (case-insensitive)."""

    target = (name or "").lower()
    for node in iter_nodes(config):
        node_name = str(node.get("name", "")).lower()
        if node_name == target:
            return node
    return None
