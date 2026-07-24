from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    llm_provider: str = "deepseek"
    kimi_api_key: str | None = None
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "kimi-k2.6"
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://models.sjtu.edu.cn/api/v1"
    deepseek_model: str = "deepseek-chat"
    ai_api_key: str | None = None
    ai_api_base: str | None = None
    ai_model: str | None = None
    llm_timeout_seconds: float = 180
    frontend_origins: str = "http://localhost:5173"
    auth_secret: str = "change-this-secret-before-production"
    auth_token_hours: int = 72
    local_auth_enabled: bool = True
    portal_session_secret: str | None = None
    portal_session_cookie_name: str = "session"
    portal_session_max_age_seconds: int = 604800
    portal_login_url: str = "https://ai4edu.sjtu.edu.cn/auth/jaccount/login"
    portal_logout_url: str = "https://ai4edu.sjtu.edu.cn/auth/logout"
    public_app_url: str = "http://localhost:5173"
    app_base_path: str = "/"
    admin_username: str = "admin"
    admin_password: str = "admin12345"
    admin_display_name: str = "系统管理员"
    database_url: str = "postgresql://siyuan:siyuan_password@localhost:5432/siyuan_compass"

    model_config = SettingsConfigDict(env_file=ROOT_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    @property
    def effective_deepseek_api_key(self) -> str | None:
        return self.deepseek_api_key or self.ai_api_key

    @property
    def effective_deepseek_base_url(self) -> str:
        return self.ai_api_base or self.deepseek_base_url

    @property
    def effective_deepseek_model(self) -> str:
        return self.ai_model or self.deepseek_model

    @property
    def jaccount_enabled(self) -> bool:
        return bool(self.portal_session_secret and self.portal_login_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
