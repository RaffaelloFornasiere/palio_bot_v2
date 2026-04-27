"""Authentication for core write endpoints.

Two accepted credentials, checked in order:
  * `PALIO_CORE_TOKEN` — pre-shared static bearer used by adapters (CLI,
    Telegram, eval runner) over loopback.
  * Firebase Google ID token issued by the web sign-in flow. Verified
    against Firebase's JWKS (via `google-auth`); the token's email must
    appear in `EDITOR_ALLOWED_EMAILS`.

If neither `PALIO_CORE_TOKEN` nor `FIREBASE_PROJECT_ID` is configured,
the dependency is a no-op so the dev/loopback deployment keeps working.
"""

from __future__ import annotations

import logging
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from palio_bot.core.config import CoreConfig

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


def _verify_firebase_id_token(token: str, config: CoreConfig) -> Optional[dict]:
    """Return the verified token claims, or None on any failure.

    Uses google-auth's Firebase verifier which handles JWKS fetch/cache,
    issuer/audience/expiry checks. Lazy-imported so the dep is only loaded
    when Firebase is actually configured.
    """
    if not config.firebase_project_id:
        return None
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token
    except ImportError:
        logger.error("google-auth is not installed; cannot verify Firebase token")
        return None

    try:
        claims = google_id_token.verify_firebase_token(
            token,
            google_requests.Request(),
            audience=config.firebase_project_id,
        )
    except Exception as exc:  # noqa: BLE001 — verifier raises a mix of types
        logger.info("firebase token verification failed: %s", exc)
        return None

    if not claims:
        return None
    if claims.get("aud") != config.firebase_project_id:
        return None
    allowed = config.allowed_emails_set()
    email = (claims.get("email") or "").lower()
    if not email or not claims.get("email_verified"):
        return None
    if allowed and email not in allowed:
        logger.warning("firebase login denied: %s not in allowlist", email)
        return None
    return claims


def _auth_configured(config: CoreConfig) -> bool:
    return bool(config.bearer_token) or bool(config.firebase_project_id)


def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> None:
    """FastAPI dependency: enforce bearer auth when configured.

    No-op when neither PALIO_CORE_TOKEN nor FIREBASE_PROJECT_ID is set,
    preserving the unauthenticated localhost/dev mode.
    """
    config: CoreConfig = request.app.state.config
    if not _auth_configured(config):
        return

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="missing bearer token")

    token = credentials.credentials

    if config.bearer_token and secrets.compare_digest(token, config.bearer_token):
        return

    if _verify_firebase_id_token(token, config) is not None:
        return

    raise HTTPException(status_code=401, detail="invalid or expired token")
