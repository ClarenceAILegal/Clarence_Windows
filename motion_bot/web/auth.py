"""Simple shared-password session auth."""

from __future__ import annotations

import hmac
import os
import secrets
from typing import Optional

from starlette.requests import Request

SESSION_AUTH_KEY = "motion_bot_authenticated"
ENV_PASSWORD = "MOTION_BOT_PASSWORD"
ENV_SECRET = "MOTION_BOT_SECRET_KEY"


def get_site_password() -> str:
    password = os.environ.get(ENV_PASSWORD, "").strip()
    if not password:
        raise RuntimeError(
            f"Set {ENV_PASSWORD} before starting the web UI "
            "(shared site password required)."
        )
    return password


def get_session_secret() -> str:
    secret = os.environ.get(ENV_SECRET, "").strip()
    if secret:
        return secret
    # Ephemeral secret: sessions reset on restart (fine for private local use)
    return secrets.token_hex(32)


def verify_password(candidate: str) -> bool:
    expected = get_site_password()
    return hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get(SESSION_AUTH_KEY))


def login_session(request: Request) -> None:
    request.session[SESSION_AUTH_KEY] = True


def logout_session(request: Request) -> None:
    request.session.clear()


def require_login_redirect(request: Request) -> Optional[str]:
    """Return login URL if not authenticated, else None."""
    if is_authenticated(request):
        return None
    return "/login"
