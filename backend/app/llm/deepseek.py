import httpx

from app.core.config import get_settings


def is_deepseek_configured() -> bool:
    return bool(get_settings().effective_deepseek_api_key)


async def create_deepseek_chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 10000,
    json_mode: bool = False,
) -> dict[str, str]:
    settings = get_settings()
    if not settings.effective_deepseek_api_key:
        raise RuntimeError("缺少 AI_API_KEY 或 DEEPSEEK_API_KEY，无法调用校内 DeepSeek。")

    base_url = settings.effective_deepseek_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.effective_deepseek_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.effective_deepseek_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
                **({"response_format": {"type": "json_object"}} if json_mode else {}),
            },
        )
        try:
            data = response.json()
        except ValueError as error:
            raise RuntimeError(f"DeepSeek API 返回了无法解析的响应：{response.status_code}") from error

    if response.status_code >= 400:
        message = data.get("error", {}).get("message") if isinstance(data, dict) else None
        raise RuntimeError(message or f"DeepSeek API 请求失败：{response.status_code}")

    choice = (data.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content", "").strip()
    if not content:
        raise RuntimeError("DeepSeek API 未返回报告内容。")

    return {
        "content": content,
        "modelName": data.get("model") or settings.effective_deepseek_model,
        "finishReason": choice.get("finish_reason") or "",
    }
