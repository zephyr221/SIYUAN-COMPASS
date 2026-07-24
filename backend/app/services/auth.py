from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from urllib.parse import urlsplit

from fastapi import Depends, Header, HTTPException, Request

from app.core.config import get_settings
from app.schemas.auth import AuthUser
from app.services.portal_sso import decode_portal_identity
from app.storage.json_db import find_user, upsert_jaccount_user

PASSWORD_ITERATIONS = 210_000


def normalize_username(username: str) -> str:
    return username.strip().lower()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(user: dict[str, Any]) -> str:
    settings = get_settings()
    payload = {
        "sub": user["id"],
        "role": user["role"],
        "exp": int(time.time()) + settings.auth_token_hours * 3600,
    }
    encoded_payload = _encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(
        settings.auth_secret.encode(),
        encoded_payload.encode(),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        expected = hmac.new(
            get_settings().auth_secret.encode(),
            encoded_payload.encode(),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected, _decode(encoded_signature)):
            return None
        payload = json.loads(_decode(encoded_payload))
        if int(payload["exp"]) < int(time.time()):
            return None
        return payload
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def public_user(user: dict[str, Any]) -> AuthUser:
    return AuthUser(
        id=user["id"],
        username=user["username"],
        displayName=user.get("displayName") or user["username"],
        role=user["role"],
        authSource=user.get("authSource", "local"),
    )


def _validate_cookie_request_origin(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    expected = urlsplit(get_settings().public_app_url)
    expected_origin = f"{expected.scheme}://{expected.netloc}"
    if not origin or origin.rstrip("/") != expected_origin.rstrip("/"):
        raise HTTPException(status_code=403, detail={"error": "请求来源校验失败"})


def require_user(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    settings = get_settings()
    portal_session = request.cookies.get(settings.portal_session_cookie_name)
    user = None
    if authorization and authorization.startswith("Bearer "):
        payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
        user = find_user(payload["sub"]) if payload else None
    elif portal_session:
        identity = decode_portal_identity(portal_session)
        if identity:
            _validate_cookie_request_origin(request)
            user = upsert_jaccount_user(
                username=identity["username"],
                display_name=identity["displayName"],
                is_admin=identity["isAdmin"],
            )
    if not user:
        raise HTTPException(status_code=401, detail={"error": "登录已失效，请重新登录"})
    return user


def require_admin(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail={"error": "需要管理员权限"})
    return user
