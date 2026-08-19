import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from app.speech import provider
from app.speech.xfyun_file import (
    SpeechProviderError,
    extract_transcript,
    generate_signature,
    transcribe_xfyun_file,
)


def settings(selected_provider: str = "xfyun_file", app_id: str | None = "app-id"):
    return SimpleNamespace(
        speech_provider=selected_provider,
        speech_xfyun_app_id=app_id,
        speech_xfyun_api_key="api-key",
        speech_xfyun_api_secret="api-secret",
        speech_xfyun_base_url="https://speech.example",
        speech_xfyun_language="autodialect",
        speech_xfyun_domain="edu",
        speech_xfyun_poll_interval_seconds=0.01,
        speech_xfyun_poll_timeout_seconds=1,
        speech_timeout_seconds=10,
        speech_max_file_mb=10,
        speech_daily_limit=20,
    )


class SpeechProviderTest(unittest.TestCase):
    def test_disabled_status_does_not_report_configured(self):
        with patch.object(provider, "get_settings", return_value=settings("disabled")):
            self.assertFalse(provider.get_speech_status()["configured"])

    def test_invalid_provider_is_rejected(self):
        with patch.object(provider, "get_settings", return_value=settings("unknown")):
            with self.assertRaisesRegex(RuntimeError, "SPEECH_PROVIDER=unknown"):
                provider.get_speech_provider()

    def test_transcribe_dispatches_to_xfyun_adapter(self):
        adapter = AsyncMock(return_value="识别结果")
        with (
            patch.object(provider, "get_settings", return_value=settings()),
            patch.object(provider, "transcribe_xfyun_file", adapter),
        ):
            result = asyncio.run(
                provider.transcribe_audio(
                    b"audio",
                    filename="recording.webm",
                    content_type="audio/webm",
                    language="zh-CN",
                )
            )
        self.assertEqual(result, "识别结果")
        adapter.assert_awaited_once()

    def test_signature_is_deterministic_for_same_parameters(self):
        params = {"appId": "app", "accessKeyId": "key", "fileName": "我的录音.wav"}
        self.assertEqual(generate_signature(params, "secret"), generate_signature(params, "secret"))

    def test_order_result_is_converted_to_text(self):
        order_result = {
            "lattice": [
                {
                    "json_1best": '{"st":{"rt":[{"ws":[{"cw":[{"w":"你好"}]},{"cw":[{"w":"。"}]}]}]}}'
                }
            ]
        }
        self.assertEqual(extract_transcript(order_result), "你好。")

    def test_upstream_file_result_is_returned_without_logging_audio(self):
        upload_response = SimpleNamespace(
            status_code=200,
            json=lambda: {"code": "000000", "content": {"orderId": "order-1"}},
        )
        result_response = SimpleNamespace(
            status_code=200,
            json=lambda: {
                "code": "000000",
                "content": {
                    "orderInfo": {"status": 4},
                    "orderResult": '{"lattice":[{"json_1best":"{\\"st\\":{\\"rt\\":[{\\"ws\\":[{\\"cw\\":[{\\"w\\":\\"你好\\"}]}]}]}}"}]}',
                },
            },
        )
        client = AsyncMock()
        client.post.side_effect = [upload_response, result_response]
        context = AsyncMock()
        context.__aenter__.return_value = client
        with (
            patch("app.speech.xfyun_file.get_settings", return_value=settings()),
            patch("app.speech.xfyun_file.httpx.AsyncClient", return_value=context),
        ):
            result = asyncio.run(
                transcribe_xfyun_file(
                    b"secret audio bytes",
                    filename="recording.wav",
                    content_type="audio/wav",
                    language="zh-CN",
                )
            )
        self.assertEqual(result, "你好")
        self.assertEqual(client.post.await_count, 2)

    def test_upstream_error_is_normalized(self):
        response = SimpleNamespace(status_code=500, json=lambda: {})
        client = AsyncMock()
        client.post.return_value = response
        context = AsyncMock()
        context.__aenter__.return_value = client
        with (
            patch("app.speech.xfyun_file.get_settings", return_value=settings()),
            patch("app.speech.xfyun_file.httpx.AsyncClient", return_value=context),
        ):
            with self.assertRaises(SpeechProviderError):
                asyncio.run(
                    transcribe_xfyun_file(
                        b"audio",
                        filename="recording.wav",
                        content_type="audio/wav",
                        language="zh-CN",
                    )
                )


if __name__ == "__main__":
    unittest.main()
