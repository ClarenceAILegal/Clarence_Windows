"""Simple shared-password session auth."""

from __future__ import annotations

import hmac
import os
import secrets
from typing import Optional

from starlette.requests import Request

SESSION_AUTH_KEY = "motion_bot_authenticated"
SESSION_PLAY_INTRO = "motion_bot_play_intro"
ENV_PASSWORD = "MOTION_BOT_PASSWORD"
ENV_SECRET = "MOTION_BOT_SECRET_KEY"

# Case-sensitive site password (overridable via MOTION_BOT_PASSWORD)
DEFAULT_PASSWORD = "B0ts4Justice"


def get_site_password() -> str:
    password = os.environ.get(ENV_PASSWORD)
    if password is None or password == "":
        return DEFAULT_PASSWORD
    return password


def get_session_secret() -> str:
    secret = os.environ.get(ENV_SECRET, "").strip()
    if secret:
        return secret
    # Ephemeral secret: sessions reset on restart (fine for private local use)
    # In production set MOTION_BOT_SECRET_KEY so logins survive restarts.
    return secrets.token_hex(32)


def use_https_cookies() -> bool:
    """Secure cookies when behind HTTPS / production reverse proxy."""
    flag = os.environ.get("MOTION_BOT_HTTPS", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    # Common platform signals
    if os.environ.get("RENDER") or os.environ.get("FLY_APP_NAME"):
        return True
    return False


def verify_password(candidate: str) -> bool:
    """Case-sensitive password check."""
    expected = get_site_password()
    return hmac.compare_digest(
        candidate.encode("utf-8"),
        expected.encode("utf-8"),
    )


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get(SESSION_AUTH_KEY))


def login_session(request: Request, *, play_intro: bool = True) -> None:
    request.session[SESSION_AUTH_KEY] = True
    if play_intro:
        request.session[SESSION_PLAY_INTRO] = True


def consume_intro_flag(request: Request) -> bool:
    """Return True once after login so the UI can play the ripple transition."""
    if request.session.pop(SESSION_PLAY_INTRO, False):
        return True
    return False


def logout_session(request: Request) -> None:
    request.session.clear()


def require_login_redirect(request: Request) -> Optional[str]:
    if is_authenticated(request):
        return None
    return "/login"
