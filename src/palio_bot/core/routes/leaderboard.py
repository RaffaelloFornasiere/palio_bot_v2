"""Leaderboard preview / apply endpoints.

Two-step flow:

  1. POST /api/leaderboard/preview
     Recomputes the leaderboard from current inputs (palio.json +
     palio_games_status.json) WITHOUT writing. Returns the proposed
     leaderboard plus the list of games whose entry would change vs the
     current leaderboard.json.

  2. POST /api/leaderboard/apply
     Standalone save of a previously-previewed leaderboard. Writes
     through the history layer (record_write + finalize_save) so
     `refs/palio/last_save` advances and the public webapp sees the
     new values.

Callers that already have an open session (e.g. the web editor saving
palio_games_status edits) should pass `leaderboard` to
`POST /api/sessions/{id}/commit` instead — that bundles the recompute
into the same squashed save commit. `/apply` exists for the standalone
case (Telegram `/leaderboard`, CLI) where there is no active session.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from palio_bot.core.auth import require_auth
from palio_bot.leaderboard_updater import LeaderboardUpdater
from palio_bot.models.leaderboard_models import Leaderboard
from palio_bot.stream.events import FileChangedEvent

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/leaderboard",
    tags=["leaderboard"],
    dependencies=[Depends(require_auth)],
)


class ChangedGame(BaseModel):
    id: str
    name: str


class PreviewResponse(BaseModel):
    proposed: Dict[str, Any]
    changed_games: List[ChangedGame]


class ApplyRequest(BaseModel):
    proposed: Dict[str, Any]


def _make_updater(request: Request) -> LeaderboardUpdater:
    config = request.app.state.config
    return LeaderboardUpdater(
        palio_file_path=config.palio_file_path,
        palio_games_status_path=config.palio_games_status_path,
        leaderboard_file_path=config.leaderboard_file_path,
    )


def _game_name_lookup(request: Request) -> Dict[str, str]:
    config = request.app.state.config
    try:
        with open(config.palio_file_path, "r", encoding="utf-8") as f:
            palio = json.load(f)
    except FileNotFoundError:
        return {}
    return {
        g.get("id"): g.get("name", g.get("id", ""))
        for g in palio.get("games", [])
        if g.get("id")
    }


@router.post("/preview", response_model=PreviewResponse)
def preview(request: Request) -> PreviewResponse:
    updater = _make_updater(request)
    try:
        proposed, changed_ids = updater.compute()
    except Exception as exc:
        logger.exception("leaderboard preview failed")
        raise HTTPException(status_code=500, detail=f"compute failed: {exc}")

    names = _game_name_lookup(request)
    return PreviewResponse(
        proposed=proposed,
        changed_games=[
            ChangedGame(id=gid, name=names.get(gid, gid)) for gid in changed_ids
        ],
    )


@router.post("/apply")
def apply(body: ApplyRequest, request: Request) -> Dict[str, str]:
    try:
        Leaderboard.model_validate(body.proposed)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"invalid leaderboard: {exc}")

    file_store = request.app.state.file_store
    stream = request.app.state.stream
    history = getattr(request.app.state, "history", None)
    registry = request.app.state.registry

    try:
        version = file_store.write_atomic("leaderboard", body.proposed)
    except Exception as exc:
        logger.exception("leaderboard apply: write_atomic failed")
        raise HTTPException(status_code=500, detail=f"write failed: {exc}")

    if history is not None:
        lb_name = registry.get_config("leaderboard").path.name
        try:
            history.record_write(
                file_name=lb_name,
                source="leaderboard_apply",
                committer=None,
                session_id=None,
                tool="leaderboard_recompute",
            )
            history.finalize_save(
                source="leaderboard_apply",
                committer=None,
                session_id=None,
                files_touched=[lb_name],
            )
        except Exception:
            logger.exception(
                "leaderboard apply: history layer failed; on-disk file "
                "was written but last_save did not advance"
            )

    stream.broadcast(
        FileChangedEvent(session_id="core", file="leaderboard", version=version)
    )
    return {"status": "ok", "version": version}
