from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import random
import string
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import httpx

from app.core.config import get_settings


class SpeechProviderError(RuntimeError):
    """A safe-to-display upstream speech service failure."""


class SpeechProviderTimeoutError(SpeechProviderError):
    """The upstream speech service did not finish within the configured time."""


def _signature_base_string(params: dict[str, Any]) -> str:
    """Build the sorted, URL-encoded string required by the XFYUN API."""
    parts: list[str] = []
    for key in sorted(params):
        if key == "signature":
            continue
        value = params[key]
        if value is None or value == "":
            continue
        # The official example encodes parameter values and keeps the sorted
        # parameter names as-is. quote_plus matches Java URLEncoder for spaces.
        parts.append(f"{key}={quote_plus(str(value), safe='')}")
    return "&".join(parts)


def generate_signature(params: dict[str, Any], access_key_secret: str) -> str:
    base_string = _signature_base_string(params)
    digest = hmac.new(
        access_key_secret.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def _date_time() -> str:
    # XFYUN requires a timestamp with an explicit local timezone offset.
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%dT%H:%M:%S%z")


def _signature_random() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.SystemRandom().choice(alphabet) for _ in range(16))


def _json_response(response: httpx.Response, phase: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as caught:
        if response.status_code >= 400:
            raise SpeechProviderError(f"讯飞语音转写{phase}失败（HTTP {response.status_code}）。") from caught
        raise SpeechProviderError(f"讯飞语音转写{phase}返回了无法识别的数据。") from caught
    if not isinstance(payload, dict):
        raise SpeechProviderError(f"讯飞语音转写{phase}返回了无法识别的数据。")
    if response.status_code >= 400:
        code = str(payload.get("code") or response.status_code)
        description = payload.get("descInfo") or payload.get("message")
        if isinstance(description, str) and description.strip():
            description = description.strip().replace("\n", " ")[:160]
            raise SpeechProviderError(
                f"讯飞语音转写{phase}失败（HTTP {response.status_code}，错误码 {code}）：{description}"
            )
        raise SpeechProviderError(f"讯飞语音转写{phase}失败（HTTP {response.status_code}，错误码 {code}）。")
    return payload


def _require_success(payload: dict[str, Any], phase: str) -> None:
    if str(payload.get("code", "")) == "000000":
        return
    code = str(payload.get("code") or "未知")
    description = payload.get("descInfo") or payload.get("message")
    if isinstance(description, str) and description.strip():
        description = description.strip().replace("\n", " ")[:160]
        raise SpeechProviderError(f"讯飞语音转写{phase}失败（错误码 {code}）：{description}")
    raise SpeechProviderError(f"讯飞语音转写{phase}失败（错误码 {code}），请检查服务额度和配置。")


def _decode_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _extract_words_from_sentence(sentence: Any) -> list[str]:
    sentence = _decode_json(sentence)
    if not isinstance(sentence, dict):
        return []
    if "json_1best" in sentence:
        sentence = _decode_json(sentence.get("json_1best"))
        if not isinstance(sentence, dict):
            return []
    st = sentence.get("st", sentence)
    if not isinstance(st, dict):
        return []
    words: list[str] = []
    for result in st.get("rt", []) or []:
        if not isinstance(result, dict):
            continue
        for word_segment in result.get("ws", []) or []:
            if not isinstance(word_segment, dict):
                continue
            candidates = word_segment.get("cw", []) or []
            if not isinstance(candidates, list):
                continue
            # The first candidate is the 1-best recognition result.
            if candidates and isinstance(candidates[0], dict):
                word = candidates[0].get("w")
                if isinstance(word, str):
                    words.append(word)
    return words


def extract_transcript(order_result: Any) -> str:
    decoded = _decode_json(order_result)
    if isinstance(decoded, dict):
        direct_text = decoded.get("text") or decoded.get("transcript")
        if isinstance(direct_text, str) and direct_text.strip():
            return direct_text.strip()

        # Prefer the smoothed result. lattice2 is the raw fallback when the
        # account has enabled post-processing that returns both variants.
        lattice = decoded.get("lattice") or decoded.get("lattice2") or []
        if isinstance(lattice, list):
            words: list[str] = []
            for sentence in lattice:
                words.extend(_extract_words_from_sentence(sentence))
            text = "".join(words).strip()
            if text:
                return text
    raise SpeechProviderError("没有识别到有效语音，请重新录制。")


def _language_for_xfyun(language: str, configured: str) -> str:
    # The file-transcription large model accepts autodialect (Chinese/English
    # plus dialects) or autominor (multilingual, which requires enablement).
    if configured in {"autodialect", "autominor"}:
        return configured
    return "autodialect" if language.lower().startswith(("zh", "cn")) else configured


async def transcribe_xfyun_file(
    audio: bytes,
    *,
    filename: str,
    content_type: str,
    language: str,
) -> str:
    del content_type  # The file suffix is the format hint expected by XFYUN.
    settings = get_settings()
    if not settings.speech_xfyun_app_id:
        raise RuntimeError("缺少 SPEECH_XFYUN_APP_ID，无法使用语音转写。")
    if not settings.speech_xfyun_api_key:
        raise RuntimeError("缺少 SPEECH_XFYUN_API_KEY，无法使用语音转写。")
    if not settings.speech_xfyun_api_secret:
        raise RuntimeError("缺少 SPEECH_XFYUN_API_SECRET，无法使用语音转写。")

    safe_filename = Path(filename).name or "recording.wav"
    signature_random = _signature_random()
    upload_params: dict[str, Any] = {
        "appId": settings.speech_xfyun_app_id,
        "accessKeyId": settings.speech_xfyun_api_key,
        "dateTime": _date_time(),
        "signatureRandom": signature_random,
        "fileSize": str(len(audio)),
        "fileName": safe_filename,
        # The browser may not expose the exact duration. Disabling this check
        # avoids submitting an estimate that could cause order rejection.
        "durationCheckDisable": "true",
        "language": _language_for_xfyun(language, settings.speech_xfyun_language),
        "pd": settings.speech_xfyun_domain,
        "audioMode": "fileStream",
        "eng_smoothproc": "true",
    }
    upload_headers = {
        "Content-Type": "application/octet-stream",
        "signature": generate_signature(upload_params, settings.speech_xfyun_api_secret),
    }
    upload_url = f"{settings.speech_xfyun_base_url.rstrip('/')}/v2/upload"
    result_url = f"{settings.speech_xfyun_base_url.rstrip('/')}/v2/getResult"

    try:
        async with httpx.AsyncClient(timeout=settings.speech_timeout_seconds) as client:
            upload_response = await client.post(
                upload_url,
                params=upload_params,
                headers=upload_headers,
                content=audio,
            )
            upload_payload = _json_response(upload_response, "上传")
            _require_success(upload_payload, "上传")
            upload_content = upload_payload.get("content")
            order_id = upload_content.get("orderId") if isinstance(upload_content, dict) else None
            if not isinstance(order_id, str) or not order_id:
                raise SpeechProviderError("讯飞语音转写上传未返回有效订单号。")

            deadline = time.monotonic() + max(settings.speech_xfyun_poll_timeout_seconds, 1)
            while True:
                result_params: dict[str, Any] = {
                    "appId": settings.speech_xfyun_app_id,
                    "accessKeyId": settings.speech_xfyun_api_key,
                    "dateTime": _date_time(),
                    "signatureRandom": signature_random,
                    "orderId": order_id,
                    "resultType": "transfer",
                }
                result_response = await client.post(
                    result_url,
                    params=result_params,
                    headers={
                        "Content-Type": "application/json",
                        "signature": generate_signature(result_params, settings.speech_xfyun_api_secret),
                    },
                    json={},
                )
                result_payload = _json_response(result_response, "查询")
                code = str(result_payload.get("code", ""))
                if code == "100013":
                    if time.monotonic() >= deadline:
                        raise SpeechProviderTimeoutError("讯飞语音转写等待超时，请稍后重试。")
                    await asyncio.sleep(max(settings.speech_xfyun_poll_interval_seconds, 0.2))
                    continue
                if code != "000000":
                    _require_success(result_payload, "查询")
                result_content = result_payload.get("content")
                if not isinstance(result_content, dict):
                    raise SpeechProviderError("讯飞语音转写查询返回了无法识别的数据。")
                order_info = result_content.get("orderInfo")
                if not isinstance(order_info, dict):
                    raise SpeechProviderError("讯飞语音转写查询返回了无法识别的数据。")
                try:
                    status = int(order_info.get("status", 3))
                except (TypeError, ValueError):
                    status = 3
                if status == 4:
                    return extract_transcript(result_content.get("orderResult"))
                if status == -1:
                    raise SpeechProviderError("讯飞语音转写失败，请重新录制。")
                if time.monotonic() >= deadline:
                    raise SpeechProviderTimeoutError("讯飞语音转写等待超时，请稍后重试。")
                await asyncio.sleep(max(settings.speech_xfyun_poll_interval_seconds, 0.2))
    except SpeechProviderError:
        raise
    except httpx.TimeoutException as caught:
        raise SpeechProviderTimeoutError("讯飞语音转写服务响应超时，请稍后重试。") from caught
    except httpx.RequestError as caught:
        raise SpeechProviderError("暂时无法连接讯飞语音转写服务，请稍后重试。") from caught
