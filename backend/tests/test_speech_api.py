import asyncio
from io import BytesIO
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import UploadFile

from app.api import speech


def settings():
    return SimpleNamespace(
        speech_provider="xfyun_file",
        speech_xfyun_app_id="app-id",
        speech_xfyun_api_key="api-key",
        speech_xfyun_api_secret="api-secret",
        speech_xfyun_base_url="https://speech.example",
        speech_timeout_seconds=10,
        speech_max_file_mb=1,
        speech_daily_limit=20,
        speech_quota_timezone="Asia/Shanghai",
    )


class SpeechApiTest(unittest.TestCase):
    def test_rejects_unsupported_audio_before_reserving_quota(self):
        audio = UploadFile(BytesIO(b"not audio"), filename="recording.txt", headers={"content-type": "text/plain"})
        with (
            patch.object(speech, "get_settings", return_value=settings()),
            patch.object(speech, "get_speech_status", return_value={"configured": True}),
            patch.object(speech, "reserve_speech_quota") as reserve,
        ):
            with self.assertRaisesRegex(Exception, "不支持这种音频格式"):
                asyncio.run(speech.transcribe(audio, "zh-CN", {"id": "user-1"}))
        reserve.assert_not_called()

    def test_success_returns_text_and_reserves_one_attempt(self):
        audio = UploadFile(BytesIO(b"audio"), filename="recording.webm", headers={"content-type": "audio/webm"})
        with (
            patch.object(speech, "get_settings", return_value=settings()),
            patch.object(speech, "get_speech_status", return_value={"configured": True}),
            patch.object(speech, "reserve_speech_quota") as reserve,
            patch.object(speech, "transcribe_audio", return_value="你好"),
        ):
            result = asyncio.run(speech.transcribe(audio, "zh-CN", {"id": "user-1"}))
        self.assertEqual(result, {"text": "你好"})
        reserve.assert_called_once()


if __name__ == "__main__":
    unittest.main()
