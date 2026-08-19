import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from app.services.report_generator import ReportGenerationError, generate_report


def _response() -> SimpleNamespace:
    return SimpleNamespace(
        id="response-1",
        userId="user-1",
        careerConfusions=["不知道未来适合做什么"],
        mainConfusionText="我还没有找到能够验证方向的行动",
        studentName="张同学",
        studentNumber="520000000000",
        contactInfo="student@example.com",
    )


FAILED_QUALITY = {
    "status": "failed",
    "warnings": ["路径内容过少：Plan C"],
    "fatalWarnings": ["路径内容过少：Plan C"],
}
PASSED_QUALITY = {"status": "passed", "warnings": [], "fatalWarnings": []}


class ReportGeneratorRetryTest(unittest.TestCase):
    def test_failed_first_report_is_repaired_once(self) -> None:
        completion = AsyncMock(
            side_effect=[
                {"content": "first", "modelName": "test-model", "finishReason": "stop"},
                {"content": "repaired", "modelName": "test-model", "finishReason": "stop"},
            ]
        )
        with (
            patch("app.services.report_generator.is_llm_configured", return_value=True),
            patch("app.services.report_generator.build_report_messages", return_value=[{"role": "user", "content": "prompt"}]),
            patch("app.services.report_generator.create_chat_completion", completion),
            patch(
                "app.services.report_generator.check_report_quality",
                side_effect=[FAILED_QUALITY, PASSED_QUALITY],
            ) as quality_check,
        ):
            report = asyncio.run(generate_report(_response(), SimpleNamespace(id="profile-1")))

        self.assertEqual(report.content, "repaired")
        self.assertEqual(report.retryCount, 1)
        self.assertEqual(completion.await_count, 2)
        second_messages = completion.await_args_list[1].args[0]
        self.assertIn("路径内容过少：Plan C", second_messages[-1]["content"])
        self.assertEqual(
            quality_check.call_args.kwargs["prohibited_personal_values"],
            ("张同学", "520000000000", "student@example.com"),
        )

    def test_second_quality_failure_stops_without_saving_report(self) -> None:
        completion = AsyncMock(
            side_effect=[
                {"content": "first", "modelName": "test-model", "finishReason": "stop"},
                {"content": "second", "modelName": "test-model", "finishReason": "stop"},
            ]
        )
        with (
            patch("app.services.report_generator.is_llm_configured", return_value=True),
            patch("app.services.report_generator.build_report_messages", return_value=[]),
            patch("app.services.report_generator.create_chat_completion", completion),
            patch(
                "app.services.report_generator.check_report_quality",
                side_effect=[FAILED_QUALITY, FAILED_QUALITY],
            ),
        ):
            with self.assertRaisesRegex(ReportGenerationError, "自动修复后仍未通过"):
                asyncio.run(generate_report(_response(), SimpleNamespace(id="profile-1")))

        self.assertEqual(completion.await_count, 2)


if __name__ == "__main__":
    unittest.main()
