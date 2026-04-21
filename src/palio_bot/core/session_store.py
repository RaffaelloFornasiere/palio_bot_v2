"""In-memory session store with per-session staged file content.

Sessions live in process memory only. On core restart, all sessions and
their staged edits are gone — adapters must re-create sessions on
reconnect (see docs/refactor/01_core_service_split.md).
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


class UnknownSession(Exception):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"unknown session {session_id}")


@dataclass
class Session:
    id: str
    label: str
    created_at: datetime
    staged: Dict[str, dict] = field(default_factory=dict)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}

    def create(self, label: str) -> Session:
        session = Session(
            id=str(uuid.uuid4()),
            label=label,
            created_at=datetime.now(timezone.utc),
        )
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise UnknownSession(session_id)
        return session

    def exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list(self) -> List[Session]:
        return list(self._sessions.values())

    # ---------- staged content ----------

    def stage(self, session_id: str, file_name: str, content: dict) -> None:
        session = self.get(session_id)
        session.staged[file_name] = copy.deepcopy(content)

    def unstage(self, session_id: str, file_name: str) -> None:
        session = self.get(session_id)
        session.staged.pop(file_name, None)

    def get_staged(self, session_id: str, file_name: str) -> Optional[dict]:
        session = self.get(session_id)
        staged = session.staged.get(file_name)
        return copy.deepcopy(staged) if staged is not None else None

    def staged_files(self, session_id: str) -> List[str]:
        return list(self.get(session_id).staged.keys())

    def clear_staged(self, session_id: str) -> None:
        self.get(session_id).staged.clear()
