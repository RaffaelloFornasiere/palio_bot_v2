"""Goliardic mini-games scoreboard (Borgo Dino, Super Borgo Bros).

Unauthenticated by design, like the borgo poll: anyone on the public
site can submit a run. Scores are browser-submitted and forgeable —
acceptable because this is a fun side feature that does NOT count toward
the official Palio leaderboard.

Per-game aggregation lives in ``MiniGameStore`` (dino=max, bros=sum).

Routes:
  POST /api/minigame/score    submit one finished run
  GET  /api/minigame/podium   per-game rankings + overall mini-podium
"""

from __future__ import annotations

import json
import logging
from typing import Set

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from palio_bot.core.minigame_store import GAMES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/minigame", tags=["minigame"])

_MAX_SCORE = 10_000_000


class ScoreRequest(BaseModel):
    game: str = Field(min_length=1, max_length=32)
    borgo: str = Field(min_length=1, max_length=64)
    score: int = Field(ge=0, le=_MAX_SCORE)


def _allowed_villages(request: Request) -> Set[str]:
    """Canonical borgo names from palio.json. Empty set => can't validate
    (palio.json missing/unreadable); the caller then accepts any sane
    string rather than hard-failing every submission."""
    config = request.app.state.config
    try:
        with open(config.palio_file_path, "r", encoding="utf-8") as f:
            palio = json.load(f)
    except (OSError, json.JSONDecodeError):
        logger.warning("minigame: palio.json unreadable; skipping borgo validation")
        return set()
    names: Set[str] = set(palio.get("villages") or [])
    names |= set((palio.get("villages_colors") or {}).keys())
    return names


@router.post("/score")
def submit_score(body: ScoreRequest, request: Request) -> dict:
    game = body.game.strip()
    if game not in GAMES:
        raise HTTPException(status_code=422, detail=f"gioco sconosciuto: {game}")

    borgo = body.borgo.strip()
    allowed = _allowed_villages(request)
    if allowed and borgo not in allowed:
        raise HTTPException(status_code=422, detail=f"borgo sconosciuto: {borgo}")

    store = request.app.state.minigame_store
    result = store.record(game=game, borgo=borgo, score=body.score)
    return {"status": "recorded", **result, "podium": store.podium()}


@router.get("/podium")
def podium(request: Request) -> dict:
    return request.app.state.minigame_store.podium()
