from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.speech.xfyun_file import transcribe_xfyun_file

SUPPORTED_SPEECH_PROVIDERS = {"disabled", "xfyun_file"}


def get_speech_provider() -> str:
    provider = get_settings().speech_provider.strip().lower()
    if provider not in SUPPORTED_SPEECH_PROVIDERS:
        supported = "、".join(sorted(SUPPORTED_SPEECH_PROVIDERS))
        raise RuntimeError(
            f"SPEECH_PROVIDER={provider or '<empty>'} 不受支持，可选：{supported}。"
        )
    return provider


def get_speech_status() -> dict[str, Any]:
    settings = get_settings()
    provider = get_speech_provider()
    configured = (
        provider == "xfyun_file"
        and bool(settings.speech_xfyun_app_id)
        and bool(settings.speech_xfyun_api_key)
        and bool(settings.speech_xfyun_api_secret)
    )
    return {
        "provider": provider,
        "configured": configured,
        "model": "录音文件转写大模型" if provider == "xfyun_file" else None,
        "maxFileMb": settings.speech_max_file_mb,
        "dailyLimit": settings.speech_daily_limit,
    }


def get_speech_configuration_error() -> str:
    status = get_speech_status()
    if status["provider"] == "disabled":
        return "语音转写功能尚未启用。"
    return "语音转写服务尚未配置，请联系管理员。"


async def transcribe_audio(
    audio: bytes,
    *,
    filename: str,
    content_type: str,
    language: str,
) -> str:
    provider = get_speech_provider()
    if provider == "disabled":
        raise RuntimeError(get_speech_configuration_error())
    return await transcribe_xfyun_file(
        audio,
        filename=filename,
        content_type=content_type,
        language=language,
    )
