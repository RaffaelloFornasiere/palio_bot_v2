"""Persisted Telegram bot UI settings.

Single-group bot, so there is exactly one setting file. Holds only the
`verbose` flag for now: true → emit the full event stream (thinking,
tool calls, tool results, token usage); false → emit just the agent's
final reply with a "sto lavorando" placeholder while it's working.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)


class TelegramSettings:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = Lock()
        self.verbose: bool = True
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.verbose = bool(data.get("verbose", True))
        except Exception:
            logger.exception(
                "telegram_settings: load failed at %s; using defaults", self.path
            )

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"verbose": self.verbose}),
            encoding="utf-8",
        )

    def toggle_verbose(self) -> bool:
        with self._lock:
            self.verbose = not self.verbose
            self._save()
            return self.verbose
