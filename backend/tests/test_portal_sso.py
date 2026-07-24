from flask import Flask
from flask.sessions import SecureCookieSessionInterface
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.portal_sso import decode_portal_identity


TEST_SECRET = "portal-test-secret"


def _signed_portal_cookie(payload: dict) -> str:
    portal = Flask("test-portal")
    portal.secret_key = TEST_SECRET
    serializer = SecureCookieSessionInterface().get_signing_serializer(portal)
    assert serializer is not None
    return serializer.dumps(payload)


def test_decode_portal_identity(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "portal_session_secret", TEST_SECRET)
    cookie = _signed_portal_cookie(
        {"user": {"jaccount": "Student01", "name": "测试学生", "is_admin": False}}
    )

    assert decode_portal_identity(cookie) == {
        "username": "student01",
        "displayName": "测试学生",
        "isAdmin": False,
    }


def test_jaccount_login_builds_portal_return_path(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "portal_session_secret", TEST_SECRET)
    monkeypatch.setattr(settings, "app_base_path", "/shengya")
    monkeypatch.setattr(settings, "portal_login_url", "https://ai4edu.sjtu.edu.cn/auth/jaccount/login")

    response = TestClient(app).get(
        "/api/auth/jaccount/login?next=/my-reports",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "https://ai4edu.sjtu.edu.cn/auth/jaccount/login?next="
    )
    assert "%2Fshengya%2Fapi%2Fauth%2Fjaccount%2Fcallback" in response.headers["location"]
