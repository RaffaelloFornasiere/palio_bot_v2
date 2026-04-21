"""FileStore implementation backed by core's HTTP API.

Bound to a specific `session_id`. On first `load(name)` it acquires the
file from core and caches the content. `save(name, data)` PUTs to core
and updates the cache.

Validation is server-side — save() raises FileStoreValidationError if
core returns 422.
"""

from __future__ import annotations

import copy
import logging
from typing import Dict, Set

from palio_bot.core_client.client import CoreClient, CoreClientError
from palio_bot.file_store import (
    FileStoreLockConflict,
    FileStoreNotFound,
    FileStoreReadOnly,
    FileStoreUnknown,
    FileStoreValidationError,
)

logger = logging.getLogger(__name__)


class RemoteFileStore:
    def __init__(self, client: CoreClient, session_id: str = "") -> None:
        self.client = client
        self.session_id = session_id
        self._cache: Dict[str, dict] = {}
        self._acquired: Set[str] = set()

    def rebind(self, session_id: str) -> None:
        """Point this store at a different session (or clear it with '').

        Resets the local acquire/cache state so the next load() hits core.
        """
        self.session_id = session_id
        self._cache.clear()
        self._acquired.clear()

    def load(self, file_name: str) -> dict:
        self._ensure_acquired(file_name)
        return copy.deepcopy(self._cache[file_name])

    def save(self, file_name: str, data: dict) -> None:
        self._ensure_acquired(file_name)
        try:
            self.client.put_file(self.session_id, file_name, data)
        except CoreClientError as exc:
            self._translate(file_name, exc)
        self._cache[file_name] = copy.deepcopy(data)

    def _ensure_acquired(self, file_name: str) -> None:
        if file_name in self._acquired:
            return
        try:
            result = self.client.acquire(self.session_id, file_name)
        except CoreClientError as exc:
            self._translate(file_name, exc)
            raise  # unreachable — _translate always raises
        self._cache[file_name] = result["content"]
        self._acquired.add(file_name)

    @staticmethod
    def _translate(file_name: str, exc: CoreClientError) -> None:
        detail = exc.detail
        if exc.status_code == 404:
            if isinstance(detail, str) and "session" in detail.lower():
                raise exc  # session gone — not a file-store error
            raise FileStoreNotFound(file_name) if isinstance(detail, str) and (
                "not found" in detail.lower()
            ) else FileStoreUnknown(file_name)
        if exc.status_code == 403:
            raise FileStoreReadOnly(file_name)
        if exc.status_code == 409:
            holder = (
                detail.get("holder_session_id") if isinstance(detail, dict) else None
            )
            raise FileStoreLockConflict(file_name, holder)
        if exc.status_code == 422:
            message = detail if isinstance(detail, str) else str(detail)
            raise FileStoreValidationError(message)
        raise exc
