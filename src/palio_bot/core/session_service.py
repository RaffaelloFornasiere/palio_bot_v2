"""Session service — composes locks, sessions, file I/O, and events.

This is the business layer routes call into. Routes deal only with HTTP
concerns (path params, status codes); all state transitions happen here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

from palio_bot.core.stream import Stream
from palio_bot.core.file_store_local import (
    LocalFileStore,
    ReadOnlyFile,
    UnknownFile,
    compute_version,
)
from palio_bot.core.lock_manager import LockConflict, LockManager
from palio_bot.core.session_store import Session, SessionStore, UnknownSession
from palio_bot.stream.events import (
    FileChangedEvent,
    LockAcquiredEvent,
    SessionCommittedEvent,
    SessionDiscardedEvent,
    SessionStartedEvent,
)
from palio_bot.tools.file_registry import FileRegistry

logger = logging.getLogger(__name__)


class ValidationFailed(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotLockHolder(Exception):
    def __init__(self, file_name: str, session_id: str, holder: Optional[str]) -> None:
        self.file_name = file_name
        self.session_id = session_id
        self.holder = holder
        super().__init__(
            f"session {session_id} does not hold {file_name} (held by {holder})"
        )


@dataclass
class AcquireResult:
    content: dict
    version: str


class SessionService:
    def __init__(
        self,
        *,
        registry: FileRegistry,
        file_store: LocalFileStore,
        session_store: SessionStore,
        lock_manager: LockManager,
        stream: Stream,
        on_commit: Optional[Callable[[List[str]], None]] = None,
    ) -> None:
        self.registry = registry
        self.file_store = file_store
        self.session_store = session_store
        self.lock_manager = lock_manager
        self.stream = stream
        self.on_commit = on_commit
        # Files that have been PUT (not just seeded) by each session. Only
        # dirty files are written on commit and trigger file_changed events.
        self._dirty: Dict[str, Set[str]] = {}

    # ---------- session lifecycle ----------

    def create_session(self, label: str) -> Session:
        session = self.session_store.create(label)
        self._dirty[session.id] = set()
        self.stream.broadcast(
            SessionStartedEvent(session_id=session.id, label=label)
        )
        logger.info("core: session %s started (label=%s)", session.id, label)
        return session

    def list_sessions(self) -> List[dict]:
        out: List[dict] = []
        for s in self.session_store.list():
            out.append(
                {
                    "id": s.id,
                    "label": s.label,
                    "created_at": s.created_at.isoformat(),
                    "files_held": self.lock_manager.held_by(s.id),
                    "files_dirty": sorted(self._dirty.get(s.id, set())),
                }
            )
        return out

    # ---------- per-file operations ----------

    def acquire(self, session_id: str, file_name: str) -> AcquireResult:
        self._require_session(session_id)
        if self.registry.get_config(file_name) is None:
            raise UnknownFile(file_name)

        # Lock first — raises LockConflict if held by another session.
        self.lock_manager.acquire(file_name, session_id)

        # Seed staged content from canonical if not already present.
        staged = self.session_store.get_staged(session_id, file_name)
        if staged is None:
            content = self.file_store.read(file_name)
            self.session_store.stage(session_id, file_name, content)
            staged = content

        version = compute_version(staged)
        self.stream.broadcast(
            LockAcquiredEvent(session_id=session_id, file=file_name)
        )
        return AcquireResult(content=staged, version=version)

    def put(self, session_id: str, file_name: str, content: dict) -> str:
        self._require_session(session_id)
        self._require_holder(session_id, file_name)

        config = self.registry.get_config(file_name)
        if config is None:
            raise UnknownFile(file_name)
        if not config.allow_edit:
            raise ReadOnlyFile(file_name)

        ok, err = self.registry.validate_content(file_name, content)
        if not ok:
            raise ValidationFailed(err or "validation failed")

        self.session_store.stage(session_id, file_name, content)
        self._dirty.setdefault(session_id, set()).add(file_name)
        return compute_version(content)

    def commit(self, session_id: str) -> Dict[str, str]:
        session = self.session_store.get(session_id)
        dirty = sorted(self._dirty.get(session_id, set()))

        versions: Dict[str, str] = {}
        for file_name in dirty:
            staged = session.staged.get(file_name)
            if staged is None:
                continue
            versions[file_name] = self.file_store.write_atomic(file_name, staged)

        released = self.lock_manager.release_all(session_id)

        for file_name in versions:
            self.stream.broadcast(
                FileChangedEvent(
                    session_id=session_id,
                    file=file_name,
                    version=versions[file_name],
                )
            )

        self.stream.broadcast(
            SessionCommittedEvent(
                session_id=session_id,
                files=list(versions.keys()),
                locks_released=released,
            )
        )

        self._dirty.pop(session_id, None)
        self.session_store.delete(session_id)

        if self.on_commit is not None and versions:
            try:
                self.on_commit(list(versions.keys()))
            except Exception:
                logger.exception("core: on_commit hook raised; ignored")

        logger.info(
            "core: session %s committed %d file(s): %s",
            session_id,
            len(versions),
            list(versions.keys()),
        )
        return versions

    def discard(self, session_id: str) -> None:
        self._require_session(session_id)
        released = self.lock_manager.release_all(session_id)
        self._dirty.pop(session_id, None)
        self.session_store.delete(session_id)
        self.stream.broadcast(
            SessionDiscardedEvent(session_id=session_id, locks_released=released)
        )
        logger.info("core: session %s discarded (released=%s)", session_id, released)

    # ---------- helpers ----------

    def _require_session(self, session_id: str) -> None:
        if not self.session_store.exists(session_id):
            raise UnknownSession(session_id)

    def _require_holder(self, session_id: str, file_name: str) -> None:
        holder = self.lock_manager.holder(file_name)
        if holder != session_id:
            raise NotLockHolder(file_name, session_id, holder)
