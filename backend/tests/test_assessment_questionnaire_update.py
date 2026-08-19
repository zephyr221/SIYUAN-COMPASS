from pathlib import Path
import unittest


FRONTEND_SOURCE = Path("../frontend/src/pages/AssessmentPage.tsx").read_text(encoding="utf-8")
SCHEMA_SOURCE = Path("app/schemas/assessment.py").read_text(encoding="utf-8")
VALIDATOR_SOURCE = Path("app/services/assessment_validator.py").read_text(encoding="utf-8")


class AssessmentQuestionnaireUpdateTest(unittest.TestCase):
    def test_removed_questions_are_not_rendered(self):
        for label in [
            "你的学校是？",
            "你对当前教育路径规划的确定程度是多少？",
            "英语成绩或证书",
            "科研、竞赛、论文或项目经历",
            "请举一个近期坚持或没有坚持下来的真实例子。",
            "面对他人负面评价时，你的典型反应是什么？",
        ]:
            self.assertNotIn(label, FRONTEND_SOURCE)

    def test_optional_identity_and_required_hometown_are_consistent(self):
        self.assertNotIn('"studentName": "请填写姓名"', VALIDATOR_SOURCE)
        self.assertNotIn('"studentNumber": "请填写学号"', VALIDATOR_SOURCE)
        self.assertIn('"hometown": "请填写家乡或主要成长地"', VALIDATOR_SOURCE)

    def test_collected_field_requiredness_matches_frontend_copy(self):
        for label in ["姓名（选填）", "学号（选填）", "联系方式（选填）"]:
            self.assertIn(label, FRONTEND_SOURCE)
        for field in ["gender", "fiveYearIncome", "tenYearIncome"]:
            self.assertIn(f'"{field}":', VALIDATOR_SOURCE)
        self.assertIn("你的性别是？", FRONTEND_SOURCE)
        self.assertIn("5年后预期收入", FRONTEND_SOURCE)
        self.assertIn("10年后预期收入", FRONTEND_SOURCE)
        self.assertNotIn("敏感生涯支持信息", FRONTEND_SOURCE)

    def test_multi_select_limits_and_other_fields_are_validated(self):
        self.assertIn("len(input_data.educationPathReasons) > 3", VALIDATOR_SOURCE)
        self.assertIn("len(input_data.preferredWorkStyle) > 2", VALIDATOR_SOURCE)
        for field in [
            "doctoralCareerOther",
            "educationPathReasonOther",
            "currentPreparationOther",
            "jobInfoChannelOther",
            "careerConfusionOther",
        ]:
            self.assertIn(field, SCHEMA_SOURCE)
            self.assertIn(field, VALIDATOR_SOURCE)

    def test_academic_competitiveness_fields_are_required(self):
        for field in ["currentGpa", "gpaScale", "majorRank", "majorTotal"]:
            self.assertIn(f'"{field}":', VALIDATOR_SOURCE)


if __name__ == "__main__":
    unittest.main()
