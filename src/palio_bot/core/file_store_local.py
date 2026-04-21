"""Canonical file I/O for core.

Reads and writes against `data/*.json` go through here. Writes are atomic
(tmp-file + os.replace in the same directory). Session staging lives in
`SessionStore`, not here — this class only knows about canonical on-disk
state.
"""

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
from pathlib import Path

from palio_bot.tools.file_registry import FileRegistry

logger = logging.getLogger(__name__)


class UnknownFile(Exception):
    def __init__(self, file_name: str) -> None:
        self.file_name = file_name
        super().__init__(f"unknown file {file_name}")


class ReadOnlyFile(Exception):
    def __init__(self, file_name: str) -> None:
        self.file_name = file_name
        super().__init__(f"{file_name} is read-only")


def compute_version(data: dict) -> str:
    """Content-addressed version — stable for identical dicts."""
    serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:12]


class LocalFileStore:
    def __init__(self, registry: FileRegistry) -> None:
        self.registry = registry

    def exists(self, file_name: str) -> bool:
        config = self.registry.get_config(file_name)
        return config is not None and config.path.exists()

    def read(self, file_name: str) -> dict:
        config = self.registry.get_config(file_name)
        if config is None:
            raise UnknownFile(file_name)
        if not config.path.exists():
            raise FileNotFoundError(config.path)
        with open(config.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write_atomic(self, file_name: str, data: dict) -> str:
        config = self.registry.get_config(file_name)
        if config is None:
            raise UnknownFile(file_name)
        if not config.allow_edit:
            raise ReadOnlyFile(file_name)

        target: Path = config.path
        target.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            dir=target.parent,
            prefix=target.name + ".",
            suffix=".writing",
            encoding="utf-8",
        ) as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp_path = Path(tmp.name)

        tmp_path.replace(target)
        logger.info("core: wrote %s (version=%s)", target, compute_version(data))
        return compute_version(data)
