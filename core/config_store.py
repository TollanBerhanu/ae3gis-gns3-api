"""Helpers for reading and writing generated configuration files."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, MutableMapping
import contextlib


@dataclass(slots=True)
class ConfigStore:
    """Manage the generated config JSON used by scripts and API."""

    path: Path

    @classmethod
    def from_path(cls, path: str | os.PathLike[str]) -> "ConfigStore":
        return cls(Path(path))

    def load(self, *, default: Mapping[str, Any] | None = None) -> MutableMapping[str, Any]:
        if not self.path.exists():
            if default is not None:
                return dict(default)
            raise FileNotFoundError(self.path)
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("Config file must contain a JSON object")
        return dict(data)

    def write(self, data: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_name = tempfile.mkstemp(prefix=self.path.name, dir=str(self.path.parent))
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=4)
                handle.write("\n")
            os.replace(tmp_name, self.path)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp_name)

    def backup(self, suffix: str = ".backup.json") -> Path:
        backup_path = self.path.with_suffix(suffix)
        try:
            shutil.copyfile(self.path, backup_path)
        except FileNotFoundError:
            pass
        return backup_path
