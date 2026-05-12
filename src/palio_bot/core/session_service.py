"""Session service — write-through with git-backed history.

This is the business layer routes call into. Routes deal only with HTTP
concerns (path params, status codes); all state transitions happen here.

Concurrency model:
  * `acquire` returns canonical content + version (no in-memory staging).
  * `put` validates, writes atomically to disk, records a per-write git
    commit through `HistoryService`. Each PUT is a real on-disk change
    and a real commit.
  * `commit` squashes every per-PUT commit since `last_save` into one
    and moves `last_save` to the new HEAD (festival-day tag is created
    lazily if the day rolled over).
  * `discard` restores every touched file to its `last_save` state and
    records a `cancel session <id>` commit.

The system today assumes a single active editor (CLI / agent / webapp
edit) at a time. Multi-writer conflict resolution is out of scope —
revisit when warranted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from palio_bot.core.stream import Stream
from palio_bot.core.file_store_local import (
    LocalFileStore,
    ReadOnlyFile,
    UnknownFile,
    compute_version,
)
from palio_bot.core.history import HistoryService
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
        history: Optional[HistoryService] = None,
        on_commit: Optional[Callable[[List[str]], None]] = None,
    ) -> None:
        self.registry = registry
        self.file_store = file_store
        self.session_store = session_store
        self.stream = stream
        self.history = history
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
        """Return canonical content + version. No in-memory staging."""
        self._require_session(session_id)
        if self.registry.get_config(file_name) is None:
            raise UnknownFile(file_name)
        content = self.file_store.read(file_name)
        return AcquireResult(content=content, version=compute_version(content))

    def put(
        self,
        session_id: str,
        file_name: str,
        content: dict,
        tool: Optional[str] = None,
    ) -> str:
        """Write-through: validates, writes to disk, records a per-write
        git commit. Each PUT is its own commit. Squashed at `commit()`.
        """
        self._require_session(session_id)
        session = self.session_store.get(session_id)

        config = self.registry.get_config(file_name)
        if config is None:
            raise UnknownFile(file_name)
        if not config.allow_edit:
            raise ReadOnlyFile(file_name)

        ok, err = self.registry.validate_content(file_name, content)
        if not ok:
            raise ValidationFailed(err or "validation failed")

        version = self.file_store.write_atomic(file_name, content)
        self._dirty.setdefault(session_id, set()).add(file_name)

        if self.history is not None:
            try:
                source, committer = _parse_session_label(session.label)
                self.history.record_write(
                    file_name=config.path.name,
                    source=source,
                    committer=committer,
                    session_id=session_id,
                    tool=tool,
                )
            except Exception:
                logger.exception("core: history.record_write failed; ignored")

        self.stream.broadcast(
            FileChangedEvent(
                session_id=session_id,
                file=file_name,
                version=version,
            )
        )
        return version

    def commit(self, session_id: str) -> Dict[str, str]:
        """Finalise the session: squash all per-PUT commits since
        `last_save` into one, move `last_save`, maybe daily-tag.
        Returns {file_name: version} for every file the session touched.
        """
        self._require_session(session_id)
        session = self.session_store.get(session_id)
        dirty = sorted(self._dirty.get(session_id, set()))

        versions: Dict[str, str] = {}
        for file_name in dirty:
            try:
                versions[file_name] = compute_version(
                    self.file_store.read(file_name)
                )
            except FileNotFoundError:
                continue

        if self.history is not None and dirty:
            try:
                source, committer = _parse_session_label(session.label)
                basenames = [
                    self.registry.get_config(n).path.name for n in dirty
                ]
                self.history.finalize_save(
                    source=source,
                    committer=committer,
                    session_id=session_id,
                    files_touched=basenames,
                )
            except Exception:
                logger.exception("core: history.finalize_save failed; ignored")

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

    # ---------- history / revert ----------

    def list_session_history(
        self, session_id: str, file_name: str, limit: int = 10
    ) -> List[Dict]:
        """Per-file list of intra-session commits (since `last_save`).

        Returns numbered entries with `step` = 1 for most recent.
        """
        self._require_session(session_id)
        if self.registry.get_config(file_name) is None:
            raise UnknownFile(file_name)
        if self.history is None:
            return []
        basename = self.registry.get_config(file_name).path.name
        commits = self.history.list_session_commits(basename, limit=limit)
        out: List[Dict] = []
        for i, c in enumerate(commits, start=1):
            out.append({
                "step": i,
                "summary": c.summary,
                "ts_iso": c.ts.isoformat(),
                "tool": c.tool,
            })
        return out

    def revert(
        self, session_id: str, file_name: str, n_steps: int
    ) -> Optional[str]:
        """Revert `file_name` by `n_steps` commits within the session.
        Returns the new HEAD SHA, or None if out of range.
        """
        self._require_session(session_id)
        session = self.session_store.get(session_id)
        config = self.registry.get_config(file_name)
        if config is None:
            raise UnknownFile(file_name)
        if self.history is None:
            return None
        source, committer = _parse_session_label(session.label)
        basename = config.path.name
        new_sha = self.history.revert_steps(
            file_name=basename, n_steps=n_steps,
            source=source, committer=committer,
        )
        if new_sha is not None:
            self._dirty.setdefault(session_id, set()).add(file_name)
            try:
                version = compute_version(self.file_store.read(file_name))
                self.stream.broadcast(FileChangedEvent(
                    session_id=session_id, file=file_name, version=version,
                ))
            except FileNotFoundError:
                pass
        return new_sha

    def discard(self, session_id: str) -> None:
        """Cancel the session: restore every touched file to its
        `last_save` state and commit a `cancel session <id>` marker.
        """
        self._require_session(session_id)
        session = self.session_store.get(session_id)
        dirty = sorted(self._dirty.get(session_id, set()))

        if self.history is not None and dirty:
            try:
                source, committer = _parse_session_label(session.label)
                basenames = [
                    self.registry.get_config(n).path.name for n in dirty
                ]
                self.history.revert_session_files(
                    files_touched=basenames,
                    source=source,
                    committer=committer,
                    session_id=session_id,
                )
                # Broadcast file-changed so adapters re-fetch the
                # rolled-back canonical state.
                for n in dirty:
                    try:
                        version = compute_version(self.file_store.read(n))
                        self.stream.broadcast(FileChangedEvent(
                            session_id=session_id, file=n, version=version,
                        ))
                    except FileNotFoundError:
                        continue
            except Exception:
                logger.exception("core: history.revert_session_files failed; ignored")

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


def _parse_session_label(label: str) -> tuple[str, Optional[str]]:
    """Split a session label into (source, committer).

    Adapters currently pass plain labels like "cli", "telegram", "agent".
    Future labels may encode an end-user identifier as
    "<adapter>:<committer>" (e.g. "telegram:@forna_tg"). Until then,
    `committer` is None and we record only the adapter source.
    """
    if not label:
        return ("unknown", None)
    if ":" in label:
        source, committer = label.split(":", 1)
        return (source.strip() or "unknown", committer.strip() or None)
    return (label.strip(), None)
