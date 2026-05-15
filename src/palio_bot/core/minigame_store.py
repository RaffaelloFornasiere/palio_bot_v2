"""Standalone store for the goliardic mini-games scoreboard.

Like ``poll_store`` and for the same reasons, this is operational counter
state — NOT editorial festival data. It deliberately bypasses the
FileRegistry / HistoryService git layer and lives in ``state/`` (outside
``data/``) so a ``data/`` restore/clean can never wipe it.

The mini-games do NOT count toward the official Palio leaderboard; this
is purely for fun (a "mini-podio").

Per-game aggregation differs by game:

  * ``dino``  -> keep the single best run (``max``). A borgo's record is
    its highest score ever.
  * ``bros``  -> accumulate (``sum``). Every finished game adds that
    run's points to the borgo's running total.

On-disk shape (``state/minigame_scores.json``, gitignored)::

    {
      "version": 1,
      "scores": {
        "dino": { "Sornico": 412, "Salt": 388 },
        "bros": { "Sornico": 5300 }
      }
    }

Points mirror the official games (``leaderboard_updater`` POINT
DISTRIBUTION): per game the borghi that have played are ranked, 1st=10,
2nd=7, 3rd=5, 4th=3, 5th/last=1; the overall mini-podium is the sum
across games.

Scores are submitted by the browser and are therefore forgeable — that
is acceptable for a goliardic side feature (no auth, no Turnstile).

All reads/writes are serialised by a process lock; FastAPI runs sync
handlers on a threadpool so a ``threading.Lock`` is the right primitive.
"""

from __future__ import annotations

import json
import logging
import tempfile
import threading
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1

# game id -> (human label, aggregation mode)
GAMES: Dict[str, Dict[str, str]] = {
    "dino": {"label": "Borgo Dino", "agg": "max"},
    "bros": {"label": "Super Borgo Bros", "agg": "sum"},
}

# Same scheme as the official games (leaderboard_updater POINT
# DISTRIBUTION). Positions beyond the table get the "last" value.
_POINTS = {1: 10, 2: 7, 3: 5, 4: 3, 5: 1}
_LAST_POINTS = 1


class MiniGameStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    # ---------- io ----------

    def _empty(self) -> dict:
        return {"version": _SCHEMA_VERSION, "scores": {g: {} for g in GAMES}}

    def _load(self) -> dict:
        if not self.path.exists():
            return self._empty()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            logger.exception("minigame: %s unreadable/corrupt; starting empty", self.path)
            return self._empty()
        if not isinstance(data, dict):
            return self._empty()
        data.setdefault("version", _SCHEMA_VERSION)
        scores = data.get("scores")
        if not isinstance(scores, dict):
            scores = {}
        for g in GAMES:
            if not isinstance(scores.get(g), dict):
                scores[g] = {}
        data["scores"] = scores
        return data

    def _save_atomic(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # `.writing` suffix matches the gitignore so the temp file is
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

    def record(self, *, game: str, borgo: str, score: int) -> dict:
        """Record one finished run. Returns the borgo's new stored value.

        ``dino`` keeps the max; ``bros`` accumulates the sum.
        """
        agg = GAMES[game]["agg"]
        with self._lock:
            data = self._load()
            table: Dict[str, int] = data["scores"][game]
            prev = int(table.get(borgo, 0))
            if agg == "max":
                new_val = max(prev, score)
            else:  # sum
                new_val = prev + score
            table[borgo] = new_val
            self._save_atomic(data)
            logger.info(
                "minigame: %s %s +%d -> %d (%s)", game, borgo, score, new_val, agg
            )
            return {"game": game, "borgo": borgo, "value": new_val, "added": score}

    def podium(self) -> dict:
        """Per-game rankings (with points) plus the overall mini-podium."""
        with self._lock:
            data = self._load()
            scores: Dict[str, Dict[str, int]] = data["scores"]

        games_out: Dict[str, dict] = {}
        overall_points: Dict[str, int] = {}
        overall_breakdown: Dict[str, Dict[str, int]] = {}

        for game, meta in GAMES.items():
            table = scores.get(game, {})
            # Only borghi that actually played rank for that game.
            ranked = sorted(
                table.items(), key=lambda kv: (-int(kv[1]), kv[0].lower())
            )
            ranking = []
            for position, (borgo, value) in enumerate(ranked, 1):
                pts = _POINTS.get(position, _LAST_POINTS)
                ranking.append(
                    {
                        "borgo": borgo,
                        "score": int(value),
                        "position": position,
                        "points": pts,
                    }
                )
                overall_points[borgo] = overall_points.get(borgo, 0) + pts
                overall_breakdown.setdefault(borgo, {})[game] = pts
            games_out[game] = {"label": meta["label"], "ranking": ranking}

        overall_sorted = sorted(
            overall_points.items(), key=lambda kv: (-kv[1], kv[0].lower())
        )
        overall = [
            {
                "borgo": borgo,
                "points": pts,
                "position": position,
                "by_game": overall_breakdown.get(borgo, {}),
            }
            for position, (borgo, pts) in enumerate(overall_sorted, 1)
        ]

        return {"games": games_out, "overall": overall}
