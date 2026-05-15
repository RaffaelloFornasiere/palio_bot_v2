"""Standalone store for the "best borgo" popularity poll.

Deliberately NOT part of the FileRegistry / git history layer. The poll
is operational counter state (like ``session.json``), not editorial
festival data: it has no draft-vs-saved distinction and needs no
rollback, so it must not touch ``refs/palio/last_save`` (a public vote
landing mid-editor-session would otherwise publish the editor's draft).

Dedup is one vote per ``client_id`` per festival-day. ``client_id`` is a
browser-generated UUID kept in ``localStorage`` — best-effort device
identity, not authentication. Real flood resistance is Cloudflare
Turnstile on the route, not this file.

On-disk shape (``state/borgo_poll.json``, gitignored — deliberately
OUTSIDE ``data/`` so a ``data/`` restore/clean can never wipe it)::

    {
      "version": 1,
      "days":   { "2026-05-15": { "Sornico": 3, "Salt": 1 } },
      "voters": { "<client_id>": ["2026-05-15"] }
    }

All reads/writes are serialised by a process lock; FastAPI runs sync
handlers on a threadpool so a ``threading.Lock`` is the right primitive.
"""

from __future__ import annotations

import json
import logging
import tempfile
import threading
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1


class PollStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    # ---------- io ----------

    def _empty(self) -> dict:
        return {"version": _SCHEMA_VERSION, "days": {}, "voters": {}}

    def _load(self) -> dict:
        if not self.path.exists():
            return self._empty()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            logger.exception("poll: %s unreadable/corrupt; starting empty", self.path)
            return self._empty()
        # Be defensive about shape — never let a bad file 500 a vote.
        if not isinstance(data, dict):
            return self._empty()
        data.setdefault("version", _SCHEMA_VERSION)
        if not isinstance(data.get("days"), dict):
            data["days"] = {}
        if not isinstance(data.get("voters"), dict):
            data["voters"] = {}
        return data

    def _save_atomic(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # `.writing` suffix matches data/.gitignore so the temp file is
        # never accidentally tracked.
        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            dir=self.path.parent,
            prefix=self.path.name + ".",
            suffix=".writing",
            encoding="utf-8",
        ) as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp_path = Path(tmp.name)
        tmp_path.replace(self.path)

    # ---------- ops ----------

    def record_vote(self, *, client_id: str, borgo: str, day: str) -> str:
        """Record one vote. Returns "recorded" or "already_voted".

        Idempotent per (client_id, festival-day): a second vote the same
        day is a no-op, not an error.
        """
        with self._lock:
            data = self._load()
            voters: Dict[str, List[str]] = data["voters"]
            if day in voters.get(client_id, []):
                return "already_voted"
            voters.setdefault(client_id, []).append(day)
            day_counts: Dict[str, int] = data["days"].setdefault(day, {})
            day_counts[borgo] = int(day_counts.get(borgo, 0)) + 1
            self._save_atomic(data)
            logger.info("poll: vote recorded (day=%s, borgo=%s)", day, borgo)
            return "recorded"

    def status(self, *, client_id: str, day: str) -> dict:
        """Per-device gate for the frontend prompt logic."""
        with self._lock:
            data = self._load()
            days = data["voters"].get(client_id, [])
        return {"ever_voted": bool(days), "voted_today": day in days}

    def stats(self, *, day: str) -> dict:
        """Aggregate counts only — never exposes client_ids."""
        with self._lock:
            data = self._load()
            days: Dict[str, Dict[str, int]] = data["days"]
        totals: Dict[str, int] = {}
        for counts in days.values():
            for borgo, n in counts.items():
                totals[borgo] = totals.get(borgo, 0) + int(n)
        today_counts = dict(days.get(day, {}))
        return {
            "today": day,
            "today_counts": today_counts,
            "today_votes": sum(today_counts.values()),
            "total_counts": totals,
            "total_votes": sum(totals.values()),
        }
