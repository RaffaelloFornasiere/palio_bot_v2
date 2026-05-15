"""Public "qual e il borgo migliore" popularity poll.

Unauthenticated by design (no `require_auth` dependency): anyone on the
public site can vote. Abuse resistance is layered, not auth:

  * `client_id` (browser localStorage UUID) -> one vote / device /
    festival-day. Stops casual honest revoting. NOT robust against a
    script (a script can mint UUIDs) — that is what Turnstile is for.
  * Cloudflare Turnstile token, verified server-side. This is the real
    anti-flood wall and is indifferent to CGNAT (so it never punishes
    many real phones sharing one carrier IP).

`TURNSTILE_SECRET` unset => verification is skipped (dev/loopback),
mirroring the `require_auth` no-op-when-unconfigured convention.

Routes:
  POST /api/poll/vote        cast (Turnstile-gated, dedup'd)
  GET  /api/poll/stats       aggregate counts (public, for the stats page)
  GET  /api/poll/status      per-device gate for the frontend prompt
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Set

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from palio_bot.core.history import festival_day

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/poll", tags=["poll"])

_TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class VoteRequest(BaseModel):
    client_id: str = Field(min_length=8, max_length=128)
    borgo: str = Field(min_length=1, max_length=64)
    turnstile_token: Optional[str] = Field(default=None, max_length=2048)


def _today() -> str:
    return festival_day(datetime.now(timezone.utc))


def _allowed_villages(request: Request) -> Set[str]:
    """Canonical borgo names from palio.json. Empty set => can't validate
    (palio.json missing/unreadable); the caller then accepts any sane
    string rather than hard-failing every vote."""
    config = request.app.state.config
    try:
        with open(config.palio_file_path, "r", encoding="utf-8") as f:
            palio = json.load(f)
    except (OSError, json.JSONDecodeError):
        logger.warning("poll: palio.json unreadable; skipping borgo validation")
        return set()
    names: Set[str] = set(palio.get("villages") or [])
    names |= set((palio.get("villages_colors") or {}).keys())
    return names


def _verify_turnstile(token: Optional[str], secret: str, remote_ip: Optional[str]) -> bool:
    """Server-side Turnstile check. Fails closed: any missing token or
    transport error rejects the vote (abuse resistance was the point)."""
    if not token:
        return False
    try:
        import httpx
    except ImportError:
        logger.error("poll: httpx missing; cannot verify Turnstile -> reject")
        return False
    payload = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    try:
        resp = httpx.post(_TURNSTILE_VERIFY_URL, data=payload, timeout=5.0)
        resp.raise_for_status()
        body = resp.json()
    except Exception as exc:  # noqa: BLE001 — network/JSON: treat all as fail
        logger.warning("poll: Turnstile verify failed (%s) -> reject", exc)
        return False
    ok = bool(body.get("success"))
    if not ok:
        logger.info("poll: Turnstile rejected token: %s", body.get("error-codes"))
    return ok


@router.post("/vote")
def vote(body: VoteRequest, request: Request) -> dict:
    config = request.app.state.config
    secret = getattr(config, "turnstile_secret", None)
    if secret:
        remote_ip = request.headers.get("cf-connecting-ip") or (
            request.client.host if request.client else None
        )
        if not _verify_turnstile(body.turnstile_token, secret, remote_ip):
            raise HTTPException(status_code=403, detail="verifica anti-bot fallita")
    else:
        logger.debug("poll: TURNSTILE_SECRET unset; skipping verification (dev)")

    borgo = body.borgo.strip()
    allowed = _allowed_villages(request)
    if allowed and borgo not in allowed:
        raise HTTPException(status_code=422, detail=f"borgo sconosciuto: {borgo}")

    store = request.app.state.poll_store
    day = _today()
    outcome = store.record_vote(client_id=body.client_id, borgo=borgo, day=day)
    return {"status": outcome, "day": day, "stats": store.stats(day=day)}


@router.get("/stats")
def stats(request: Request) -> dict:
    store = request.app.state.poll_store
    return store.stats(day=_today())


@router.get("/status")
def status(client_id: str, request: Request) -> dict:
    if not (8 <= len(client_id) <= 128):
        raise HTTPException(status_code=422, detail="client_id non valido")
    store = request.app.state.poll_store
    return store.status(client_id=client_id, day=_today())
