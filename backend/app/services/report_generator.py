from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from app.llm.provider import create_chat_completion, get_llm_configuration_error, is_llm_configured
from app.schemas.assessment import AssessmentResponse
from app.schemas.profile import CareerProfile
from app.schemas.report import CareerBlueprintReport
from app.services.report_prompt import build_report_messages
from app.services.profile_prompt import redact_model_forbidden_values
from app.services.report_quality_check import check_report_quality, count_chineseish_words

REPORT_PROMPT_VERSION = "career-blueprint-v1.1.0"


class ReportGenerationError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


ProgressCallback = Callable[[str, int, str], None]


async def generate_report(
    response: AssessmentResponse,
    profile: CareerProfile,
    progress_callback: ProgressCallback | None = None,
) -> CareerBlueprintReport:
    if not is_llm_configured():
        raise ReportGenerationError(get_llm_configuration_error())

    now = now_iso()
    messages = build_report_messages(response, profile)
    result: dict[str, str] | None = None
    quality = None
    retry_count = 0
    for attempt in range(2):
        if progress_callback:
            if attempt == 0:
                progress_callback("report_generating", 65, "正在基于原始问卷和结构化画像生成六模块三路径报告。")
            else:
                progress_callback("report_retrying", 82, "报告质量门禁未通过，正在自动修复结构、证据和行动建议。")
        try:
            result = await create_chat_completion(messages, max_tokens=10000)
        except Exception as error:
            raise ReportGenerationError(f"大模型调用失败：{error}") from error

        if progress_callback:
            progress_callback("report_validating", 88, "报告已返回，正在检查结构、证据、路径差异、行动项和隐私信息。")
        quality = check_report_quality(
            result["content"],
            expected_confusions=response.careerConfusions,
            main_confusion_text=response.mainConfusionText,
            prohibited_personal_values=(
                response.studentName,
                response.studentNumber,
                response.contactInfo,
            ),
            finish_reason=result.get("finishReason"),
        )
        if quality["status"] != "failed":
            retry_count = attempt
            break
        if attempt == 0:
            fatal_warnings = quality.get("fatalWarnings") or quality["warnings"]
            messages = [
                *messages,
                {
                    "role": "assistant",
                    "content": redact_model_forbidden_values(result["content"], response),
                },
                {
                    "role": "user",
                    "content": (
                        "上一版报告未通过质量门禁。请完整重写并只输出修复后的Markdown报告，不要解释。"
                        f"必须修复：{'；'.join(fatal_warnings)}。"
                        "保留有依据的内容，确保六个模块完整、三条路径实质不同、每条路径有验证行动或切换条件，"
                        "第四模块包含3—5个编号行动项，并且不得输出姓名、学号或联系方式。"
                    ),
                },
            ]

    if not result or quality is None:
        raise ReportGenerationError("大模型未返回可用报告。")
    if quality["status"] == "failed":
        fatal_warnings = quality.get("fatalWarnings") or quality["warnings"]
        nonfatal_warnings = [item for item in quality["warnings"] if item not in fatal_warnings]
        warning_suffix = f"；普通警告：{'；'.join(nonfatal_warnings)}" if nonfatal_warnings else ""
        raise ReportGenerationError(f"大模型返回的报告经自动修复后仍未通过质量校验：{'；'.join(fatal_warnings)}{warning_suffix}")

    return CareerBlueprintReport(
        id=str(uuid4()),
        userId=response.userId,
        responseId=response.id,
        profileId=profile.id,
        title="我的生涯蓝图",
        content=result["content"],
        wordCount=count_chineseish_words(result["content"]),
        generationStatus="success",
        qualityStatus=quality["status"],
        errorMessage="；".join(quality["warnings"]) or None,
        modelName=result["modelName"],
        promptVersion=REPORT_PROMPT_VERSION,
        inputSnapshot={"response": response, "profile": profile},
        retryCount=retry_count,
        createdAt=now,
        updatedAt=now,
    )
