from urllib.parse import urlencode, urljoin, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.schemas.auth import AuthResult, AuthUser, ChangePasswordInput, LoginInput, RegisterInput
from app.services.auth import (
    create_access_token,
    hash_password,
    normalize_username,
    public_user,
    require_user,
    verify_password,
)
from app.core.config import get_settings
from app.storage.json_db import create_account, find_user_by_username, update_user_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResult)
def register(input_data: RegisterInput) -> AuthResult:
    if not get_settings().local_auth_enabled:
        raise HTTPException(status_code=404, detail={"error": "本地账号注册已关闭"})
    username = normalize_username(input_data.username)
    if not username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail={"error": "用户名只能包含字母、数字、下划线和连字符"})
    if find_user_by_username(username):
        raise HTTPException(status_code=409, detail={"error": "用户名已存在"})

    user = create_account(
        username=username,
        display_name=input_data.displayName.strip(),
        password_hash=hash_password(input_data.password),
        role="student",
    )
    return AuthResult(token=create_access_token(user), user=public_user(user))


@router.post("/login", response_model=AuthResult)
def login(input_data: LoginInput) -> AuthResult:
    if not get_settings().local_auth_enabled:
        raise HTTPException(status_code=404, detail={"error": "请使用 jAccount 登录"})
    user = find_user_by_username(normalize_username(input_data.username))
    if not user or not verify_password(input_data.password, user.get("passwordHash", "")):
        raise HTTPException(status_code=401, detail={"error": "用户名或密码错误"})
    return AuthResult(token=create_access_token(user), user=public_user(user))


@router.get("/me", response_model=AuthUser)
def me(user=Depends(require_user)) -> AuthUser:
    return public_user(user)


@router.post("/change-password")
def change_password(input_data: ChangePasswordInput, user=Depends(require_user)) -> dict[str, str]:
    if user.get("authSource") != "local" or not get_settings().local_auth_enabled:
        raise HTTPException(status_code=400, detail={"error": "jAccount 密码请在学校统一身份平台修改"})
    if not verify_password(input_data.currentPassword, user.get("passwordHash", "")):
        raise HTTPException(status_code=400, detail={"error": "当前密码不正确"})
    if input_data.currentPassword == input_data.newPassword:
        raise HTTPException(status_code=400, detail={"error": "新密码不能与当前密码相同"})
    if not update_user_password(user["id"], hash_password(input_data.newPassword)):
        raise HTTPException(status_code=404, detail={"error": "用户不存在"})
    return {"message": "密码修改成功"}


def _safe_app_path(value: str | None, fallback: str = "/assessment") -> str:
    settings = get_settings()
    base_path = settings.app_base_path.rstrip("/") or ""
    candidate = (value or "").strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        candidate = fallback
    if base_path and not candidate.startswith(f"{base_path}/"):
        candidate = f"{base_path}{candidate if candidate.startswith('/') else '/' + candidate}"
    return candidate


@router.get("/jaccount/login")
def jaccount_login(next_path: str | None = Query(default=None, alias="next")):
    settings = get_settings()
    if not settings.jaccount_enabled:
        raise HTTPException(status_code=503, detail={"error": "jAccount 登录尚未配置"})

    callback_path = f"{settings.app_base_path.rstrip('/')}/api/auth/jaccount/callback"
    callback_query = urlencode({"next": _safe_app_path(next_path)})
    portal_next = f"{callback_path}?{callback_query}"
    separator = "&" if "?" in settings.portal_login_url else "?"
    return RedirectResponse(
        url=f"{settings.portal_login_url}{separator}{urlencode({'next': portal_next})}",
        status_code=302,
    )


@router.get("/jaccount/callback")
def jaccount_callback(
    next_path: str | None = Query(default=None, alias="next"),
    user=Depends(require_user),
):
    del user
    target = _safe_app_path(next_path)
    return RedirectResponse(url=urljoin(get_settings().public_app_url.rstrip("/") + "/", target.lstrip("/")), status_code=302)


@router.get("/logout")
def logout():
    settings = get_settings()
    parsed = urlsplit(settings.portal_logout_url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=500, detail={"error": "退出地址配置错误"})
    return RedirectResponse(url=settings.portal_logout_url, status_code=302)
