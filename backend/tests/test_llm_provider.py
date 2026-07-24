import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from app.llm import provider


def settings(selected_provider: str = "kimi") -> SimpleNamespace:
    values = SimpleNamespace(
        llm_provider=selected_provider,
        kimi_api_key="kimi-key",
        kimi_base_url="https://api.moonshot.cn/v1",
        kimi_model="kimi-k2.6",
        deepseek_api_key="deepseek-key",
        deepseek_base_url="https://api.deepseek.com",
        deepseek_model="deepseek-chat",
        effective_deepseek_api_key="deepseek-key",
        effective_deepseek_base_url="https://models.sjtu.edu.cn/api/v1",
        effective_deepseek_model="deepseek-chat",
    )
    return values


class LlmProviderTest(unittest.TestCase):
    def test_status_uses_selected_provider(self) -> None:
        with patch.object(provider, "get_settings", return_value=settings("deepseek")):
            self.assertEqual(
                provider.get_llm_status(),
                {
                    "provider": "deepseek",
                    "configured": True,
                    "model": "deepseek-chat",
                    "baseUrl": "https://models.sjtu.edu.cn/api/v1",
                    "apiKeyVariable": "AI_API_KEY 或 DEEPSEEK_API_KEY",
                },
            )

    def test_invalid_provider_is_rejected(self) -> None:
        with patch.object(provider, "get_settings", return_value=settings("unknown")):
            with self.assertRaisesRegex(RuntimeError, "LLM_PROVIDER=unknown"):
                provider.get_llm_provider()

    def test_chat_completion_dispatches_to_kimi(self) -> None:
        kimi_call = AsyncMock(return_value={"content": "ok"})
        deepseek_call = AsyncMock(return_value={"content": "wrong"})
        with (
            patch.object(provider, "get_settings", return_value=settings("kimi")),
            patch.object(provider, "create_kimi_chat_completion", kimi_call),
            patch.object(provider, "create_deepseek_chat_completion", deepseek_call),
        ):
            result = asyncio.run(
                provider.create_chat_completion(
                    [{"role": "user", "content": "hello"}],
                    json_mode=True,
                )
            )

        self.assertEqual(result, {"content": "ok"})
        kimi_call.assert_awaited_once_with(
            [{"role": "user", "content": "hello"}],
            max_tokens=10000,
            json_mode=True,
        )
        deepseek_call.assert_not_awaited()

    def test_chat_completion_dispatches_to_deepseek(self) -> None:
        deepseek_call = AsyncMock(return_value={"content": "ok"})
        with (
            patch.object(provider, "get_settings", return_value=settings("deepseek")),
            patch.object(provider, "create_deepseek_chat_completion", deepseek_call),
        ):
            result = asyncio.run(
                provider.create_chat_completion([{"role": "user", "content": "hello"}])
            )

        self.assertEqual(result, {"content": "ok"})
        deepseek_call.assert_awaited_once_with(
            [{"role": "user", "content": "hello"}],
            temperature=0.4,
            max_tokens=10000,
            json_mode=False,
        )


if __name__ == "__main__":
    unittest.main()
