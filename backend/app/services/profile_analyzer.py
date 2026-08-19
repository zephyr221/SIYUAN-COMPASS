from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from pydantic import ValidationError

from app.llm.provider import create_chat_completion, get_llm_configuration_error, is_llm_configured
from app.schemas.assessment import AssessmentResponse
from app.schemas.profile import CareerProfile, ProfileAnalysisResult
from app.services.profile_prompt import (
    PROFILE_PROMPT_VERSION,
    build_profile_messages,
    redact_model_forbidden_values,
)


class ProfileAnalysisError(RuntimeError):
    pass


def _parse_profile_json(content: str) -> ProfileAnalysisResult:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    if not cleaned.startswith("{"):
        object_start = cleaned.find("{")
        object_end = cleaned.rfind("}")
        if object_start >= 0 and object_end > object_start:
            cleaned = cleaned[object_start : object_end + 1]

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ProfileAnalysisError(
            f"画像模型返回的JSON无法解析：{error.msg}（第{error.lineno}行，第{error.colno}列）"
        ) from error

    if not isinstance(payload, dict):
        raise ProfileAnalysisError("画像模型返回的JSON必须是对象。")

    try:
        analysis = ProfileAnalysisResult.model_validate(payload)
    except ValidationError as error:
        details = []
        for item in error.errors()[:5]:
            location = ".".join(str(part) for part in item["loc"]) or "root"
            details.append(f"{location} {item['msg']}")
        remaining = len(error.errors()) - len(details)
        suffix = f"；另有{remaining}项错误" if remaining > 0 else ""
        raise ProfileAnalysisError(f"画像JSON字段校验失败：{'；'.join(details)}{suffix}") from error

    has_core_content = any(
        [
            analysis.summary.strip(),
            analysis.coreMotivations,
            analysis.verifiedStrengths,
            analysis.potentialStrengths,
            analysis.keyRisks,
            analysis.visionConsistency,
            analysis.educationPathAssessments,
            analysis.planA,
            analysis.planB,
            analysis.planC,
        ]
    )
    if not has_core_content:
        raise ProfileAnalysisError("画像JSON没有可用于报告生成的核心分析内容。")
    return analysis


def _collect_quality_warnings(analysis: ProfileAnalysisResult) -> list[str]:
    warnings: list[str] = []
    if not analysis.summary.strip():
        warnings.append("缺少画像摘要")
    if not (analysis.verifiedStrengths or analysis.potentialStrengths):
        warnings.append("缺少优势分析")
    if not analysis.keyRisks:
        warnings.append("缺少风险分析")
    if not analysis.educationPathAssessments:
        warnings.append("缺少教育路径判断")
    if not analysis.planA:
        warnings.append("缺少 Plan A")
    if not analysis.planB:
        warnings.append("缺少 Plan B")
    if not analysis.planC:
        warnings.append("缺少 Plan C")
    if not analysis.reportEvidenceMap:
        warnings.append("缺少报告证据映射")
    return warnings


ProgressCallback = Callable[[str, int, str], None]


async def analyze_career_profile(
    response: AssessmentResponse,
    progress_callback: ProgressCallback | None = None,
) -> CareerProfile:
    if not is_llm_configured():
        raise ProfileAnalysisError(get_llm_configuration_error())

    result: dict[str, str] | None = None
    analysis: ProfileAnalysisResult | None = None
    retry_reason: str | None = None

    for attempt in range(2):
        if progress_callback:
            if attempt == 0:
                progress_callback("profile_generating", 20, "正在根据每道题的用途和交叉规则生成结构化用户画像。")
            else:
                progress_callback(
                    "profile_retrying",
                    35,
                    f"画像结构未通过校验，正在自动修正：{retry_reason or '未知原因'}",
                )
        try:
            result = await create_chat_completion(
                build_profile_messages(response, retry_reason),
                temperature=0.1,
                max_tokens=10000,
                json_mode=True,
            )
        except Exception as error:
            raise ProfileAnalysisError(f"用户画像生成失败：{error}") from error

        try:
            if progress_callback:
                progress_callback("profile_validating", 45, "画像已返回，正在校验证据、矛盾和三路径结构。")
            analysis = _parse_profile_json(
                redact_model_forbidden_values(result["content"], response)
            )
            break
        except ProfileAnalysisError as error:
            finish_reason = result.get("finishReason") or "unknown"
            retry_reason = f"{error}；finish_reason={finish_reason}"
            if attempt == 1:
                raise ProfileAnalysisError(f"{retry_reason}；已自动重试1次仍失败") from error

    if not result or not analysis:
        raise ProfileAnalysisError("用户画像生成失败：模型未返回可用的结构化画像。")

    return CareerProfile(
        **analysis.model_dump(),
        id=str(uuid4()),
        userId=response.userId,
        responseId=response.id,
        modelName=result["modelName"],
        promptVersion=PROFILE_PROMPT_VERSION,
        createdAt=datetime.now(timezone.utc).isoformat(),
        qualityWarnings=_collect_quality_warnings(analysis),
        evidence=[
            evidence
            for finding in [*analysis.coreMotivations, *analysis.verifiedStrengths, *analysis.potentialStrengths, *analysis.keyRisks]
            for evidence in finding.evidence
        ][:20],
        strengthTags=[item.title for item in [*analysis.verifiedStrengths, *analysis.potentialStrengths]],
        riskTags=[item.title for item in analysis.keyRisks],
        valueTags=response.topValuesRanked,
        interestTags=[item.title for item in analysis.potentialStrengths],
    )
