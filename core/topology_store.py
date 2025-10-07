"""File-based persistence for topology definitions."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4


class TopologyNotFoundError(LookupError):
    """Raised when a topology record cannot be located."""


class TopologyRepository:
    """Persist topology records as individual JSON files."""

    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _path_for(self, topology_id: str) -> Path:
        return self._storage_dir / f"{topology_id}.json"

    @staticmethod
    def _timestamp() -> str:
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _dump(path: Path, payload: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")

    @staticmethod
    def _serialize(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        serialised: list[dict[str, Any]] = []
        for record in records:
            document = dict(record)
            serialised.append(document)
        return serialised

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        topology_id = str(uuid4())
        now = self._timestamp()
        payload = {
            "id": topology_id,
            "name": data["name"],
            "description": data.get("description"),
            "scenario": data["scenario"],
            "created_at": now,
            "updated_at": now,
        }
        self._dump(self._path_for(topology_id), payload)
        return dict(payload)

    def list_all(self) -> list[dict[str, Any]]:
        records = []
        for path in sorted(self._storage_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            records.append(self._load(path))
        return records

    def get(self, topology_id: str) -> dict[str, Any]:
        path = self._path_for(topology_id)
        if not path.exists():
            raise TopologyNotFoundError(topology_id)
        return self._load(path)

    def update(self, topology_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        path = self._path_for(topology_id)
        if not path.exists():
            raise TopologyNotFoundError(topology_id)
        payload = self._load(path)
        payload.update({k: v for k, v in updates.items() if k in {"name", "description", "scenario"}})
        payload["updated_at"] = self._timestamp()
        self._dump(path, payload)
        return payload

    def delete(self, topology_id: str) -> None:
        path = self._path_for(topology_id)
        if not path.exists():
            raise TopologyNotFoundError(topology_id)
        path.unlink()
