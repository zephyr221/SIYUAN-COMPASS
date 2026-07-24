from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.llm.deepseek import create_deepseek_chat_completion
from app.llm.kimi import create_kimi_chat_completion

SUPPORTED_LLM_PROVIDERS = {"kimi", "deepseek"}


def get_llm_provider() -> str:
    provider = get_settings().llm_provider.strip().lower()
    if provider not in SUPPORTED_LLM_PROVIDERS:
        supported = "、".join(sorted(SUPPORTED_LLM_PROVIDERS))
        raise RuntimeError(f"LLM_PROVIDER={provider or '<empty>'} 不受支持，可选：{supported}。")
    return provider


def get_llm_status() -> dict[str, Any]:
    settings = get_settings()
    provider = get_llm_provider()
    if provider == "deepseek":
        return {
            "provider": provider,
            "configured": bool(settings.effective_deepseek_api_key),
            "model": settings.effective_deepseek_model,
            "baseUrl": settings.effective_deepseek_base_url,
            "apiKeyVariable": "AI_API_KEY 或 DEEPSEEK_API_KEY",
        }
    return {
        "provider": provider,
        "configured": bool(settings.kimi_api_key),
        "model": settings.kimi_model,
        "baseUrl": settings.kimi_base_url,
        "apiKeyVariable": "KIMI_API_KEY",
    }


def is_llm_configured() -> bool:
    return bool(get_llm_status()["configured"])


def get_llm_configuration_error() -> str:
    status = get_llm_status()
    return f"大模型未配置，请检查 {status['apiKeyVariable']}。"


async def create_chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 10000,
    json_mode: bool = False,
) -> dict[str, str]:
    provider = get_llm_provider()
    if provider == "deepseek":
        return await create_deepseek_chat_completion(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )
    return await create_kimi_chat_completion(
        messages,
        max_tokens=max_tokens,
        json_mode=json_mode,
    )
