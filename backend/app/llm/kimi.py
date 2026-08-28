import json

import httpx

from app.core.config import get_settings
from app.llm.http_client import build_llm_timeout, describe_llm_transport_error


def is_kimi_configured() -> bool:
    return bool(get_settings().kimi_api_key)


async def create_kimi_chat_completion(
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 10000,
    json_mode: bool = False,
) -> dict[str, str]:
    settings = get_settings()
    if not settings.kimi_api_key:
        raise RuntimeError("缺少 KIMI_API_KEY，无法调用 Kimi。")

    base_url = settings.kimi_base_url.rstrip("/")
    content_parts: list[str] = []
    finish_reason = ""
    model_name = settings.kimi_model
    reasoning_length = 0

    try:
        async with httpx.AsyncClient(
            timeout=build_llm_timeout(settings.llm_timeout_seconds)
        ) as client:
            async with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.kimi_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.kimi_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "stream": True,
                    "thinking": {"type": "disabled"},
                    **({"response_format": {"type": "json_object"}} if json_mode else {}),
                },
            ) as response:
                if response.status_code >= 400:
                    raw_error = await response.aread()
                    try:
                        error_data = json.loads(raw_error)
                    except (json.JSONDecodeError, TypeError):
                        error_data = None
                    message = (
                        error_data.get("error", {}).get("message")
                        if isinstance(error_data, dict)
                        else None
                    )
                    raise RuntimeError(message or f"Kimi API 请求失败：{response.status_code}")

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    model_name = chunk.get("model") or model_name
                    choice = (chunk.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}
                    reasoning_content = delta.get("reasoning_content") or ""
                    content_delta = delta.get("content") or ""
                    reasoning_length += len(reasoning_content)
                    if content_delta:
                        content_parts.append(content_delta)
                    if choice.get("finish_reason"):
                        finish_reason = choice["finish_reason"]
    except httpx.RequestError as error:
        raise RuntimeError(
            describe_llm_transport_error("Kimi", settings.llm_timeout_seconds, error)
        ) from error

    content = "".join(content_parts).strip()
    if not content:
        detail = f"结束原因：{finish_reason or '未知'}，推理内容长度：{reasoning_length}"
        raise RuntimeError(f"Kimi API 未返回报告正文（{detail}）。")

    return {
        "content": content,
        "modelName": model_name,
        "finishReason": finish_reason,
    }
