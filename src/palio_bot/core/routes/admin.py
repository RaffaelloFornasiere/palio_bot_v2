"""Admin endpoints — dev/test use only.

`POST /admin/reset` is used by the eval harness to drop all in-flight
sessions and optionally replace canonical files with scenario seeds.
"""

import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from palio_bot.core.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", dependencies=[Depends(require_auth)])

_MANAGED_FILE_ATTRS = (
    "palio_file_path",
    "palio_games_status_path",
    "leaderboard_file_path",
)


class ResetBody(BaseModel):
    seeds_dir: Optional[str] = None


@router.post("/reset")
async def reset(body: ResetBody, request: Request):
    svc = request.app.state.session_service
    config = request.app.state.config

    # Drop every in-flight session + its locks.
    for session in list(svc.session_store.list()):
        svc.discard(session.id)

    if body.seeds_dir:
        seeds_dir = Path(body.seeds_dir)
        if not seeds_dir.is_dir():
            raise HTTPException(status_code=400, detail=f"seeds_dir not found: {seeds_dir}")

        for attr in _MANAGED_FILE_ATTRS:
            target: Path = getattr(config, attr)
            seed = seeds_dir / target.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if seed.exists():
                shutil.copy2(seed, target)
                logger.info("admin/reset: copied %s -> %s", seed, target)
            elif target.exists():
                target.unlink()
                logger.info("admin/reset: removed %s (no seed provided)", target)

    return {"ok": True}
