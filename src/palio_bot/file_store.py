"""FileStore protocol — the seam between `MultiJSONEditorTool` and storage.

Two implementations:
- `DirectFileStore` (this module) reads/writes canonical files directly.
  Used in-process, no sessions, no network. Validates via FileRegistry.
- `RemoteFileStore` (`palio_bot.core_client.file_store_remote`) talks to
  `palio_bot.core` over HTTP. Used by adapters.

The Protocol is synchronous so the tool stays synchronous (the existing
agent loop already blocks on sync file I/O; localhost HTTP is equivalent).
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

from palio_bot.tools.file_registry import FileRegistry

logger = logging.getLogger(__name__)


class FileStoreError(Exception):
    """Base class for FileStore failures."""


class FileStoreNotFound(FileStoreError):
    def __init__(self, file_name: str) -> None:
        self.file_name = file_name
        super().__init__(f"file not found: {file_name}")


class FileStoreUnknown(FileStoreError):
    def __init__(self, file_name: str) -> None:
        self.file_name = file_name
        super().__init__(f"unknown file: {file_name}")


class FileStoreReadOnly(FileStoreError):
    def __init__(self, file_name: str) -> None:
        self.file_name = file_name
        super().__init__(f"{file_name} is read-only")


class FileStoreValidationError(FileStoreError):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class FileStoreLockConflict(FileStoreError):
    def __init__(self, file_name: str, holder_session_id: str | None) -> None:
        self.file_name = file_name
        self.holder_session_id = holder_session_id
        super().__init__(f"{file_name} is held by session {holder_session_id}")


class FileStore(Protocol):
    def load(self, file_name: str) -> dict: ...
    def save(self, file_name: str, data: dict) -> None: ...


class DirectFileStore:
    """In-process file store over a FileRegistry.

    Reads `get_active_path` (temp if present, otherwise canonical). Writes
    atomically to the active path and runs Pydantic + village-whitelist
    validation before persisting. Mirrors the old tool's behavior exactly
    so eval scenarios can run without core.
    """

    def __init__(self, registry: FileRegistry) -> None:
        self.registry = registry

    def load(self, file_name: str) -> dict:
        config = self.registry.get_config(file_name)
        if config is None:
            raise FileStoreUnknown(file_name)
        path = self.registry.get_active_path(file_name)
        if path is None or not path.exists():
            raise FileStoreNotFound(file_name)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, file_name: str, data: dict) -> None:
        config = self.registry.get_config(file_name)
        if config is None:
            raise FileStoreUnknown(file_name)
        if not config.allow_edit:
            raise FileStoreReadOnly(file_name)

        ok, err = self.registry.validate_content(file_name, data)
        if not ok:
            raise FileStoreValidationError(err or "validation failed")

        path = self.registry.get_active_path(file_name)
        if path is None:
            raise FileStoreNotFound(file_name)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.registry.mark_modified(file_name)
