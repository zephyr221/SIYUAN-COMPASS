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
    llm_timeout_seconds: float = 600
    speech_provider: str = "disabled"
    speech_xfyun_app_id: str | None = None
    speech_xfyun_api_key: str | None = None
    speech_xfyun_api_secret: str | None = None
    speech_xfyun_base_url: str = "https://office-api-ist-dx.iflyaisol.com"
    speech_xfyun_language: str = "autodialect"
    speech_xfyun_domain: str = "edu"
    speech_xfyun_poll_interval_seconds: float = 1.5
    speech_xfyun_poll_timeout_seconds: float = 120
    speech_timeout_seconds: float = 30
    speech_max_file_mb: int = 10
    speech_daily_limit: int = 0
    speech_quota_timezone: str = "Asia/Shanghai"
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
    assessment_submission_maintenance: bool = False
    assessment_submission_maintenance_message: str = (
        "报告生成服务正在维护，现暂停新提交和报告生成。请勿重复提交、清理浏览器缓存或更换设备，"
        "以免丢失本机已填写内容。请保留当前浏览器；恢复后请先查看结果，我们会另行通知需要补充信息的同学。"
    )
    report_generation_daily_limit: int = 0
    report_generation_quota_timezone: str = "Asia/Shanghai"
    generation_max_concurrency: int = 4
    generation_job_lease_seconds: int = 300
    generation_job_heartbeat_seconds: int = 30
    generation_job_retention_days: int = 30
    assessment_draft_retention_days: int = 30
    admin_audit_retention_days: int = 180
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
