"""Session service — sessions, staged writes, optimistic concurrency.

This is the business layer routes call into. Routes deal only with HTTP
concerns (path params, status codes); all state transitions happen here.

Concurrency model (no locks):
  * `acquire` returns a snapshot + version. Multiple sessions may hold
    staged copies of the same file simultaneously.
  * `put` validates + stages. No lock check.
  * `commit` compares the version the session was based on against the
    canonical version. If they diverged (someone else committed meanwhile)
    the commit is rejected with `VersionConflict`.
  * After a successful commit, every OTHER session that has any of the
    just-committed files in its dirty set is auto-discarded. A
    `SessionDiscardedEvent` is broadcast for each — the web editor and
    agent adapter react by resetting their UI state. This is the
    "reactive" side of the model: whoever sees the change first stays,
    the stale sessions fall off.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set

from palio_bot.core.stream import Stream
from palio_bot.core.file_store_local import (
    LocalFileStore,
    ReadOnlyFile,
    UnknownFile,
    compute_version,
)
from palio_bot.core.session_store import Session, SessionStore, UnknownSession
from palio_bot.stream.events import (
    FileChangedEvent,
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


class VersionConflict(Exception):
    def __init__(self, file_name: str, base_version: str, current_version: str) -> None:
        self.file_name = file_name
        self.base_version = base_version
        self.current_version = current_version
        super().__init__(
            f"{file_name}: version {base_version[:12]} is stale "
            f"(current is {current_version[:12]})"
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
        stream: Stream,
        on_commit: Optional[Callable[[List[str]], None]] = None,
    ) -> None:
        self.registry = registry
        self.file_store = file_store
        self.session_store = session_store
        self.stream = stream
        self.on_commit = on_commit
        # Files PUT by each session (vs. just seeded). Only dirty files are
        # written on commit and participate in conflict detection.
        self._dirty: Dict[str, Set[str]] = {}
        # Per-session, per-file: the canonical version the session saw at
        # acquire-time. Used for optimistic-concurrency checks on commit.
        self._base_versions: Dict[str, Dict[str, str]] = {}

    # ---------- session lifecycle ----------

    def create_session(self, label: str) -> Session:
        session = self.session_store.create(label)
        self._dirty[session.id] = set()
        self._base_versions[session.id] = {}
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
                    "files_dirty": sorted(self._dirty.get(s.id, set())),
                }
            )
        return out

    # ---------- per-file operations ----------

    def acquire(self, session_id: str, file_name: str) -> AcquireResult:
        self._require_session(session_id)
        if self.registry.get_config(file_name) is None:
            raise UnknownFile(file_name)

        staged = self.session_store.get_staged(session_id, file_name)
        if staged is None:
            content = self.file_store.read(file_name)
            self.session_store.stage(session_id, file_name, content)
            staged = content
            # Capture the canonical version so we can detect conflicts at
            # commit time. Only set on the first acquire — subsequent
            # re-acquires within the same session keep the original base.
            base_version = compute_version(content)
            self._base_versions.setdefault(session_id, {})[file_name] = base_version

        version = compute_version(staged)
        return AcquireResult(content=staged, version=version)

    def put(self, session_id: str, file_name: str, content: dict) -> str:
        self._require_session(session_id)

        config = self.registry.get_config(file_name)
        if config is None:
            raise UnknownFile(file_name)
        if not config.allow_edit:
            raise ReadOnlyFile(file_name)

        # Require a prior acquire so we have a base_version to compare
        # against at commit. Also seeds the staged dict.
        if self.session_store.get_staged(session_id, file_name) is None:
            canonical = self.file_store.read(file_name)
            self._base_versions.setdefault(session_id, {})[file_name] = (
                compute_version(canonical)
            )

        ok, err = self.registry.validate_content(file_name, content)
        if not ok:
            raise ValidationFailed(err or "validation failed")

        self.session_store.stage(session_id, file_name, content)
        self._dirty.setdefault(session_id, set()).add(file_name)
        return compute_version(content)

    def commit(self, session_id: str) -> Dict[str, str]:
        self._require_session(session_id)
        session = self.session_store.get(session_id)
        dirty = sorted(self._dirty.get(session_id, set()))

        # Optimistic concurrency: every dirty file's canonical version must
        # still match what the session saw at acquire-time. Otherwise some
        # other session committed in the meantime and this commit is stale.
        base_versions = self._base_versions.get(session_id, {})
        for file_name in dirty:
            base = base_versions.get(file_name)
            canonical = self.file_store.read(file_name)
            current = compute_version(canonical)
            if base is not None and base != current:
                raise VersionConflict(file_name, base, current)

        versions: Dict[str, str] = {}
        for file_name in dirty:
            staged = session.staged.get(file_name)
            if staged is None:
                continue
            versions[file_name] = self.file_store.write_atomic(file_name, staged)

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
                locks_released=[],
            )
        )

        self._dirty.pop(session_id, None)
        self._base_versions.pop(session_id, None)
        self.session_store.delete(session_id)

        # Reactive discard: any OTHER live session that had one of these
        # files dirty is now based on stale canonical content. Drop it and
        # let its client (agent adapter or web editor) notice via the WS
        # event and reset.
        if versions:
            self._discard_conflicting_sessions(
                excluded=session_id, changed_files=set(versions.keys())
            )

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
        self._dirty.pop(session_id, None)
        self._base_versions.pop(session_id, None)
        self.session_store.delete(session_id)
        self.stream.broadcast(
            SessionDiscardedEvent(session_id=session_id, locks_released=[])
        )
        logger.info("core: session %s discarded", session_id)

    # ---------- helpers ----------

    def _require_session(self, session_id: str) -> None:
        if not self.session_store.exists(session_id):
            raise UnknownSession(session_id)

    def _discard_conflicting_sessions(
        self, *, excluded: str, changed_files: Set[str]
    ) -> None:
        victims: List[str] = []
        for s in list(self.session_store.list()):
            if s.id == excluded:
                continue
            dirty = self._dirty.get(s.id, set())
            if dirty & changed_files:
                victims.append(s.id)

        for sid in victims:
            logger.info(
                "core: auto-discarding session %s (conflicts with commit)", sid
            )
            self._dirty.pop(sid, None)
            self._base_versions.pop(sid, None)
            self.session_store.delete(sid)
            self.stream.broadcast(
                SessionDiscardedEvent(session_id=sid, locks_released=[])
            )
