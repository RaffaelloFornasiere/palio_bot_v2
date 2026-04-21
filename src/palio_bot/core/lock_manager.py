"""Per-file exclusive-lock registry.

A file is owned by at most one session at a time. Re-acquire by the same
session is idempotent. Release by a non-holder is a no-op (defensive
against stale cleanup paths).
"""

from typing import Dict, List, Optional


class LockConflict(Exception):
    """Raised when a session tries to acquire a file held by another session."""

    def __init__(self, file_name: str, holder_session_id: str) -> None:
        self.file_name = file_name
        self.holder_session_id = holder_session_id
        super().__init__(f"{file_name} is held by session {holder_session_id}")


class LockManager:
    def __init__(self) -> None:
        self._locks: Dict[str, str] = {}

    def acquire(self, file_name: str, session_id: str) -> None:
        holder = self._locks.get(file_name)
        if holder is not None and holder != session_id:
            raise LockConflict(file_name, holder)
        self._locks[file_name] = session_id

    def release(self, file_name: str, session_id: str) -> None:
        if self._locks.get(file_name) == session_id:
            del self._locks[file_name]

    def release_all(self, session_id: str) -> List[str]:
        released = [f for f, s in self._locks.items() if s == session_id]
        for f in released:
            del self._locks[f]
        return released

    def holder(self, file_name: str) -> Optional[str]:
        return self._locks.get(file_name)

    def held_by(self, session_id: str) -> List[str]:
        return [f for f, s in self._locks.items() if s == session_id]
