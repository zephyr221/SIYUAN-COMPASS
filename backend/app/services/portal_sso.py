from __future__ import annotations

from functools import lru_cache
from typing import Any

from flask import Flask
from flask.sessions import SecureCookieSessionInterface
from itsdangerous import BadData

from app.core.config import get_settings


@lru_cache(maxsize=4)
def _portal_session_serializer(secret: str):
    portal_app = Flask("siyuan-compass-portal-session")
    portal_app.secret_key = secret
    return SecureCookieSessionInterface().get_signing_serializer(portal_app)


def decode_portal_identity(cookie_value: str | None) -> dict[str, Any] | None:
    settings = get_settings()
    if not cookie_value or not settings.portal_session_secret:
        return None

    serializer = _portal_session_serializer(settings.portal_session_secret)
    if serializer is None:
        return None

    try:
        session_data = serializer.loads(
            cookie_value,
            max_age=settings.portal_session_max_age_seconds,
        )
    except BadData:
        return None

    user = session_data.get("user") if isinstance(session_data, dict) else None
    if not isinstance(user, dict):
        return None

    username = str(user.get("jaccount") or "").strip().lower()
    if not username:
        return None

    display_name = str(user.get("name") or username).strip()
    return {
        "username": username,
        "displayName": display_name or username,
    }
