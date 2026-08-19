import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from app.schemas.assessment import AssessmentResponse
from app.schemas.profile import CareerProfile
from app.services.profile_analyzer import analyze_career_profile
from app.services.profile_prompt import (
    MODEL_EXCLUDED_RESPONSE_FIELDS,
    build_model_safe_response_payload,
    build_profile_messages,
)
from app.services.report_prompt import build_report_messages


FORBIDDEN_VALUES = (
    "隐私姓名-ZHANG",
    "隐私学校-SJTU",
    "PRIV-STUDENT-2026",
    "privacy-contact@example.invalid",
    "internal-response-uuid-secret",
    "internal-user-uuid-secret",
    "2099-01-01T01:02:03+00:00",
    "2099-01-01T01:02:04+00:00",
)


def make_response() -> AssessmentResponse:
    return AssessmentResponse(
        studentName=FORBIDDEN_VALUES[0],
        school=FORBIDDEN_VALUES[1],
        studentNumber=FORBIDDEN_VALUES[2],
        contactInfo=FORBIDDEN_VALUES[3],
        educationStage="本科",
        grade="大三",
        gender="隐私性别值",
        collegeMajor="计算机科学与技术",
        hometown="上海",
        mastersIntention="考虑读研",
        phdIntention="暂不考虑",
        educationPathReasons=["提升专业能力"],
        fiveYearCity="上海",
        fiveYearIncome="隐私五年收入值",
        fiveYearIndustry="软件与信息服务",
        fiveYearRole="工程师",
        fiveYearFamilyStatus="保持稳定关系",
        fiveYearHousingPlan="租住",
        fiveYearHobbiesSkills="持续写作和运动",
        tenYearCity="上海",
        tenYearIncome="隐私十年收入值",
        tenYearIndustry="软件与信息服务",
        tenYearRole="技术负责人",
        tenYearFamilyStatus="重视家庭与工作平衡",
        tenYearHousingPlan="根据情况决定",
        tenYearHobbiesSkills="保持专业学习",
        topValuesRanked=["成长", "稳定", "自主"],
        abilityScores={"logic": 4, "expression": 3, "spatialDesign": 3, "interpersonal": 3},
        interestScores={"handsOn": 4, "research": 4, "creation": 3, "helping": 3, "leadership": 2, "detail": 4},
        currentGpa="3.6",
        gpaScale="4.0",
        majorRank="12",
        majorTotal="100",
        failedCourseStatus="无",
        currentPreparations=["课程学习"],
        preparationDetails="完成过课程项目",
        missingResources=["岗位信息"],
        majorOutcomeAwareness="了解一部分",
        targetJobAwareness="正在了解",
        jobInfoChannels=["学校就业平台"],
        healthEnergyStatus="总体稳定",
        careerConfusions=["不知道未来适合做什么"],
        mainConfusionText=(
            f"{FORBIDDEN_VALUES[0]} 希望确认方向；账号线索 {FORBIDDEN_VALUES[2]}；"
            f"内部记录 {FORBIDDEN_VALUES[4]}；另留 13800138000 和 other@example.invalid。"
        ),
        userId=FORBIDDEN_VALUES[5],
        id=FORBIDDEN_VALUES[4],
        submittedAt=FORBIDDEN_VALUES[6],
        createdAt=FORBIDDEN_VALUES[7],
    )


class ModelDataMinimizationTest(unittest.TestCase):
    def test_profile_payload_excludes_identifiers_metadata_and_unused_fields(self) -> None:
        payload = build_model_safe_response_payload(make_response())

        self.assertTrue(MODEL_EXCLUDED_RESPONSE_FIELDS.isdisjoint(payload))
        self.assertEqual(payload["collegeMajor"], "计算机科学与技术")
        self.assertEqual(payload["gender"], "隐私性别值")
        self.assertNotIn("fiveYearIncome", payload)
        self.assertNotIn("tenYearIncome", payload)
        self.assertEqual(payload["careerConfusions"], ["不知道未来适合做什么"])

    def test_both_model_stages_redact_known_identifier_values(self) -> None:
        response = make_response()
        profile_messages = build_profile_messages(response)
        profile = CareerProfile(
            id="profile-id",
            userId=response.userId,
            responseId=response.id,
            modelName="test-model",
            promptVersion="test-prompt",
            createdAt=response.createdAt,
            summary="；".join(FORBIDDEN_VALUES),
        )
        report_messages = build_report_messages(response, profile)

        for messages in (profile_messages, report_messages):
            model_request = "\n".join(message["content"] for message in messages)
            for forbidden_value in FORBIDDEN_VALUES:
                self.assertNotIn(forbidden_value, model_request)
            self.assertNotIn("13800138000", model_request)
            self.assertNotIn("other@example.invalid", model_request)

    def test_raw_model_output_is_not_kept_on_profile(self) -> None:
        model_output = json.dumps(
            {"summary": f"具备可用于报告的结构化摘要；{FORBIDDEN_VALUES[0]}；13800138000"},
            ensure_ascii=False,
        )
        completion = AsyncMock(
            return_value={
                "content": model_output,
                "modelName": "test-model",
                "finishReason": "stop",
            }
        )
        with (
            patch("app.services.profile_analyzer.is_llm_configured", return_value=True),
            patch("app.services.profile_analyzer.create_chat_completion", completion),
        ):
            profile = asyncio.run(analyze_career_profile(make_response()))

        self.assertEqual(profile.summary, "具备可用于报告的结构化摘要；[已脱敏]；[已脱敏]")
        self.assertIsNone(profile.rawModelOutput)


if __name__ == "__main__":
    unittest.main()
