from __future__ import annotations

import json

from app.schemas.assessment import AssessmentResponse
from app.schemas.profile import ProfileAnalysisResult
from app.core.data_privacy import redact_obvious_contact_details
from app.services.question_rules import render_question_rules

PROFILE_PROMPT_VERSION = "profile-analysis-v1.7.0"

# These values are either direct identifiers, internal linkage metadata, or
# questionnaire fields that are not needed to produce career guidance.  Keep
# the exclusion in one place so both LLM stages use the same data boundary.
DIRECT_IDENTIFIER_FIELDS = frozenset(
    {
        "studentName",
        "school",
        "studentNumber",
        "contactInfo",
    }
)
INTERNAL_METADATA_FIELDS = frozenset(
    {
        "id",
        "userId",
        "submittedAt",
        "createdAt",
    }
)
MODEL_UNUSED_RESPONSE_FIELDS = frozenset(
    {
        "fiveYearIncome",
        "tenYearIncome",
        "educationCertainty",
        "englishCertificates",
        "academicExperiences",
        "executionCase",
        "negativeFeedbackReaction",
    }
)
MODEL_EXCLUDED_RESPONSE_FIELDS = (
    DIRECT_IDENTIFIER_FIELDS | INTERNAL_METADATA_FIELDS | MODEL_UNUSED_RESPONSE_FIELDS
)


def build_model_safe_response_payload(response: AssessmentResponse) -> dict[str, object]:
    """Return only questionnaire fields approved for external model input."""

    response_payload = response.model_dump(
        mode="json",
        exclude=MODEL_EXCLUDED_RESPONSE_FIELDS,
    )
    if response.doctoralCareerDirection != "其他发展方向":
        response_payload.pop("doctoralCareerOther", None)
    if "其他" not in response.educationPathReasons:
        response_payload.pop("educationPathReasonOther", None)
    if "其他" not in response.currentPreparations:
        response_payload.pop("currentPreparationOther", None)
    if "其他" not in response.jobInfoChannels:
        response_payload.pop("jobInfoChannelOther", None)
    if "其他" not in response.careerConfusions:
        response_payload.pop("careerConfusionOther", None)
    return response_payload


def redact_model_forbidden_values(text: str, response: AssessmentResponse) -> str:
    """Redact known identifiers if a user repeats them in another answer."""

    redacted = text
    forbidden_values: set[str] = set()
    for field_name in DIRECT_IDENTIFIER_FIELDS | INTERNAL_METADATA_FIELDS:
        value = getattr(response, field_name, None)
        if isinstance(value, str) and value.strip():
            normalized = value.strip()
            forbidden_values.add(normalized)
            # Structured profile values are JSON encoded before this final
            # safeguard, so also cover escaped newlines, quotes and slashes.
            forbidden_values.add(json.dumps(normalized, ensure_ascii=False)[1:-1])
    for forbidden_value in sorted(forbidden_values, key=len, reverse=True):
        redacted = redacted.replace(forbidden_value, "[已脱敏]")
    return redact_obvious_contact_details(redacted)


def _render_model_safe_question_rules(selected_confusions: list[str]) -> str:
    rules_payload = json.loads(render_question_rules(selected_confusions))
    question_rules = rules_payload.get("questionRules")
    if isinstance(question_rules, dict):
        for field_name in MODEL_EXCLUDED_RESPONSE_FIELDS:
            question_rules.pop(field_name, None)
    return json.dumps(rules_payload, ensure_ascii=False, separators=(",", ":"))


def build_profile_messages(response: AssessmentResponse, retry_reason: str | None = None) -> list[dict[str, str]]:
    response_payload = build_model_safe_response_payload(response)
    response_json = json.dumps(
        response_payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    schema_json = json.dumps(
        ProfileAnalysisResult.model_json_schema(),
        ensure_ascii=False,
        separators=(",", ":"),
    )

    retry_instruction = ""
    if retry_reason:
        retry_instruction = (
            f"\n上一次输出未通过校验，原因是：{retry_reason}。"
            "请只修复上述问题，并确保输出满足JSON Schema。"
            "仅当finish_reason为length或错误说明JSON无法解析时才压缩文字；字段校验失败时不要无谓删减必填字段。"
        )

    user_content = f"""
请根据“问题解释规则”和“学生回答”生成结构化用户画像JSON。问题解释规则来自问卷设计文档，是判断每道题用途的最高优先级依据。{retry_instruction}

分析流程必须按以下顺序执行：
1. 先识别客观事实和已经发生的行为证据。
2. 再识别动机、价值排序、教育意愿和5—10年愿景。
3. 根据educationStage判断本科、硕士、博士问题的适用范围；不要对博士生继续分析读硕/读博问题，也不要对本科生套用博士生出口问题。
4. 对每项自评能力、兴趣、他人称赞特质，查找行为证据；有成果、项目、竞赛、科研、实习或准备细节佐证才可进入verifiedStrengths，否则只能进入potentialStrengths。
5. 结合GPA、排名、挂科重修、二专、转专业和准备细节，判断升学、学术、就业、跨专业或复合路径可行性；信息缺失时必须标为信息缺口，不得推测。
6. 交叉检查教育意向、具体规划、目标岗位学历要求、科研兴趣、执行力、抗压、高强度承受和职业风险偏好，分别评估升学、就业、出国、体制内、企业研发等路径。
7. 检查目标城市、行业、岗位、家庭、生活安排、技能、健康精力和风险偏好之间是否一致。
8. 主动查找意愿与行动、目标与资源、5年与10年、价值偏好、风险偏好、执行力之间的矛盾。矛盾不是错误，需说明含义和验证行动。
9. 根据证据强度生成Plan A、Plan B与Plan C。Plan A是主攻路径，Plan B是备选路径，两条路径必须可切换，写清下一步和切换条件；Plan C是系统建议路径，必须跳出学生原有设定，基于优势、兴趣、限制、风险和信息缺口提出第三条值得探索的方向；第二专业或原专业能力可作为备选路径依据，但不能无证据夸大。
10. 尽量建立reportEvidenceMap，为六个报告模块列出可使用的关键证据。
11. 对学生实际选择的每一个careerConfusions选项，必须使用selectedCareerConfusionRules中的专属用途和建议，不能合并成泛化结论。

约束：
- 所有evidence和counterEvidence必须写成“字段名：回答内容或可核对事实”的形式，字段名必须使用学生回答JSON中的英文键名。
- 优先保证summary、优势、风险、教育路径判断和Plan A / Plan B / Plan C有实质内容；辅助字段缺失时可使用空数组或null。
- reportEvidenceMap建议使用JSON Schema中的六个中文模块标题；标题有轻微差异不会导致画像失败。
- verifiedStrengths至少需要一条behavior证据；没有满足条件的优势时允许为空。
- potentialStrengths用于表达尚待行为验证的能力或兴趣。
- 直接身份信息只用于系统归属，不得出现在画像JSON、证据或报告证据映射中。
- 结论信心只能为low、medium或high；路径适配只能为low、medium、high或uncertain。
- Plan A不一定是升学，应由目标匹配、真实行动和时间窗口共同决定。
- Plan C不能重复Plan A或Plan B，尤其要服务于“自己也不知道想干什么”或原有设定证据不足的学生；如果证据不足，Plan C应明确写成低成本验证方向，而不是确定结论。
- 不分析、不预测也不评价薪资、收入区间、收入目标是否现实或住房购买能力；不得在画像任何字段中出现具体薪资结论。
- 不得编造院校、岗位待遇、家庭意见或学生未提供的经历。
- 输出应紧凑，总长度控制在约3500—5000个中文字符；同一证据不要在多个字段中反复解释。
- summary不超过200字；单项conclusion、rationale或meaning不超过120字；列表只保留最关键的2—3项。
- 只输出JSON对象，不要Markdown代码块、解释文字或前后缀。

问题解释规则：
{_render_model_safe_question_rules(response.careerConfusions)}

学生回答：
{response_json}

输出必须符合以下JSON Schema：
{schema_json}
""".strip()
    user_content = redact_model_forbidden_values(user_content, response)

    return [
        {
            "role": "system",
            "content": (
                "你是一名负责高校生涯规划评估的结构化分析专家。"
                "你的任务不是撰写报告，而是依据问卷设计规则完成证据推理，并只输出合法JSON。"
                "每个结论必须引用具体回答；必须区分事实、行为、规划、信息、意愿、自评和愿景。"
                "不得把自评直接写成已验证能力，不得把意愿直接写成适配结论，不得进行医学、心理或人格诊断。"
            ),
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]
