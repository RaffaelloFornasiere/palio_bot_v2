"""Editor auth endpoints.

`GET /api/editor/config` — public: exposes the Firebase web config the
frontend needs to initialize Google sign-in. The Firebase API key is not
a secret (it's a project identifier; access is gated by allowlist +
Firebase Auth rules), so serving it over a public endpoint is standard.

`GET /api/editor/me` — requires a valid bearer (either the static
PALIO_CORE_TOKEN or a verified Firebase ID token). Lets the frontend
confirm its current token is still accepted.
"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from palio_bot.core.auth import require_auth
from palio_bot.core.config import CoreConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/editor")


class EditorConfigResponse(BaseModel):
    auth_required: bool
    firebase: dict | None = None


@router.get("/config", response_model=EditorConfigResponse)
async def editor_config(request: Request) -> EditorConfigResponse:
    config: CoreConfig = request.app.state.config
    firebase = None
    if config.firebase_project_id:
        firebase = {
            "projectId": config.firebase_project_id,
            "apiKey": config.firebase_api_key,
            "authDomain": config.firebase_auth_domain
            or f"{config.firebase_project_id}.firebaseapp.com",
            "appId": config.firebase_app_id,
        }
    return EditorConfigResponse(
        auth_required=bool(config.firebase_project_id or config.bearer_token),
        firebase=firebase,
    )


@router.get("/me")
async def me(_: None = Depends(require_auth)):
    return {"ok": True}
