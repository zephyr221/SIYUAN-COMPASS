from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.config import get_settings
from app.services.auth import require_user
from app.speech.xfyun_file import SpeechProviderError, SpeechProviderTimeoutError
from app.speech.provider import (
    get_speech_configuration_error,
    get_speech_status,
    transcribe_audio,
)
from app.storage.json_db import SpeechQuotaStorageError, reserve_speech_quota

router = APIRouter(prefix="/speech", tags=["speech"])

ALLOWED_AUDIO_TYPES = {
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "audio/wav",
    "audio/webm",
    "audio/x-m4a",
    "audio/x-wav",
}
ALLOWED_AUDIO_SUFFIXES = {".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".ogg", ".wav", ".webm"}


@router.get("/status")
def speech_status(_user=Depends(require_user)) -> dict[str, object]:
    return get_speech_status()


@router.post("/transcribe")
async def transcribe(
    audio: Annotated[UploadFile, File(description="浏览器录制的音频")],
    language: Annotated[str, Form()] = "zh-CN",
    user=Depends(require_user),
) -> dict[str, str]:
    settings = get_settings()
    status = get_speech_status()
    if not status["configured"]:
        raise HTTPException(status_code=503, detail={"error": get_speech_configuration_error()})

    content_type = (audio.content_type or "").split(";", 1)[0].strip().lower()
    filename = Path(audio.filename or "").name
    suffix = Path(filename).suffix.lower()
    suffix_is_allowed = suffix in ALLOWED_AUDIO_SUFFIXES
    type_is_allowed = content_type in ALLOWED_AUDIO_TYPES
    type_is_unknown = content_type in {"", "application/octet-stream"}
    if not (type_is_allowed or (type_is_unknown and suffix_is_allowed)):
        raise HTTPException(status_code=415, detail={"error": "不支持这种音频格式，请重新录制。"})

    max_bytes = max(settings.speech_max_file_mb, 1) * 1024 * 1024
    try:
        payload = await audio.read(max_bytes + 1)
    finally:
        await audio.close()
    if not payload:
        raise HTTPException(status_code=400, detail={"error": "录音内容为空，请重新录制。"})
    if len(payload) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail={"error": f"录音文件不能超过 {settings.speech_max_file_mb} MB。"},
        )

    quota_day = datetime.now(ZoneInfo(settings.speech_quota_timezone)).date()
    try:
        reserve_speech_quota(user["id"], quota_day, settings.speech_daily_limit)
    except SpeechQuotaStorageError as caught:
        raise HTTPException(status_code=429, detail={"error": str(caught)}) from caught

    try:
        text = await transcribe_audio(
            payload,
            filename=filename or f"recording{suffix or '.webm'}",
            content_type=content_type or "application/octet-stream",
            language=language.strip()[:20],
        )
    except SpeechProviderTimeoutError as caught:
        raise HTTPException(status_code=504, detail={"error": str(caught)}) from caught
    except SpeechProviderError as caught:
        raise HTTPException(status_code=502, detail={"error": str(caught)}) from caught
    except RuntimeError as caught:
        raise HTTPException(status_code=503, detail={"error": str(caught)}) from caught

    return {"text": text}
