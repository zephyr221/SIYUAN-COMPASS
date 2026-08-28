from __future__ import annotations

import unittest

import httpx

from app.llm.http_client import build_llm_timeout, describe_llm_transport_error


class LlmHttpClientTest(unittest.TestCase):
    def test_long_model_read_uses_shorter_connection_guards(self):
        timeout = build_llm_timeout(600)

        self.assertEqual(timeout.connect, 10)
        self.assertEqual(timeout.read, 600)
        self.assertEqual(timeout.write, 30)
        self.assertEqual(timeout.pool, 30)

    def test_timeout_message_is_actionable_and_confirms_draft_retention(self):
        request = httpx.Request("POST", "https://models.example.invalid/chat/completions")
        error = httpx.ReadTimeout("", request=request)

        message = describe_llm_transport_error("DeepSeek", 600, error)

        self.assertIn("600 秒", message)
        self.assertIn("已填写内容仍会保留", message)


if __name__ == "__main__":
    unittest.main()
