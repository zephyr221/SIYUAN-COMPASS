from __future__ import annotations

from collections.abc import Sequence
from difflib import SequenceMatcher
import re
from typing import Literal

from app.core.data_privacy import contains_obvious_contact_details

REQUIRED_SECTIONS = [
    "一、你5—10年后的人生画像",
    "二、你的核心优势与风险短板",
    "三、人生愿景与当前路径的匹配度诊断",
    "四、接下来6个月，你可以做的3—5件事",
    "五、半年后我会问你这些问题",
    "六、一个值得你长期思考的问题",
    "安全提醒",
]

REQUIRED_CONTENT = [
    "Plan A",
    "Plan B",
    "Plan C",
    "你现在最大的困惑是什么",
    "这个困惑背后的真正问题是什么",
    "接下来可以如何验证",
    "心理咨询中心",
    "就业指导中心",
]
DISCOURAGED_PHRASES = ["你必须", "你一定适合", "你不适合", "你肯定", "绝对", "唯一选择", "严重不足", "竞争力很弱"]
SECTION_MAX_LENGTHS = {
    "一、你5—10年后的人生画像": 850,
    "二、你的核心优势与风险短板": 1050,
    "三、人生愿景与当前路径的匹配度诊断": 2000,
    "四、接下来6个月，你可以做的3—5件事": 1450,
    "五、半年后我会问你这些问题": 550,
    "六、一个值得你长期思考的问题": 380,
}
SECTION_MIN_LENGTHS = {
    "一、你5—10年后的人生画像": 120,
    "二、你的核心优势与风险短板": 180,
    "三、人生愿景与当前路径的匹配度诊断": 300,
    "四、接下来6个月，你可以做的3—5件事": 260,
    "五、半年后我会问你这些问题": 100,
    "六、一个值得你长期思考的问题": 80,
}
MIN_REPORT_LENGTH = 1200
PLAN_TITLES = ("Plan A", "Plan B", "Plan C")


def count_chineseish_words(content: str) -> int:
    return len("".join(content.split()))


def _section_lengths(content: str) -> dict[str, int]:
    lengths: dict[str, int] = {}
    positions = [
        (content.find(title), title)
        for title in [*SECTION_MAX_LENGTHS, "安全提醒"]
        if content.find(title) >= 0
    ]
    positions.sort()

    for index, (start, title) in enumerate(positions):
        if title not in SECTION_MAX_LENGTHS:
            continue
        heading_end = content.find("\n", start + len(title))
        body_start = heading_end + 1 if heading_end >= 0 else start + len(title)
        if index + 1 < len(positions):
            next_title_start = positions[index + 1][0]
            next_heading_start = content.rfind("\n", 0, next_title_start)
            body_end = next_heading_start if next_heading_start >= 0 else next_title_start
        else:
            body_end = len(content)
        lengths[title] = count_chineseish_words(content[body_start:body_end])
    return lengths


def _compact(value: str) -> str:
    return "".join(value.split())


def _has_heading(content: str, title: str) -> bool:
    return bool(re.search(rf"(?m)^##\s+{re.escape(title)}\s*$", content))


def _has_subheading(content: str, title: str) -> bool:
    return bool(re.search(rf"(?m)^###\s+{re.escape(title)}(?:[：:？?].*)?$", content))


def _extract_subsection(content: str, title: str) -> str:
    match = re.search(rf"(?m)^###\s+{re.escape(title)}(?:[：:？?].*)?\s*$", content)
    if not match:
        return ""
    next_heading = re.search(r"(?m)^#{2,3}\s+", content[match.end() :])
    end = match.end() + next_heading.start() if next_heading else len(content)
    return content[match.end() : end].strip()


def _plan_warnings(content: str) -> list[str]:
    warnings: list[str] = []
    bodies = {title: _extract_subsection(content, title) for title in PLAN_TITLES}
    for title, body in bodies.items():
        if body and count_chineseish_words(body) < 80:
            warnings.append(f"路径内容过少：{title}")
        if body and not any(keyword in body for keyword in ("下一步", "验证", "行动", "条件")):
            warnings.append(f"路径缺少验证行动或切换条件：{title}")

    compact_bodies = {title: _compact(body) for title, body in bodies.items() if body}
    for index, left in enumerate(PLAN_TITLES):
        for right in PLAN_TITLES[index + 1 :]:
            if left not in compact_bodies or right not in compact_bodies:
                continue
            similarity = SequenceMatcher(None, compact_bodies[left], compact_bodies[right]).ratio()
            if similarity >= 0.78:
                warnings.append(f"路径内容高度重复：{left} 与 {right}")
    return warnings


def _contains_meaningful_snippet(content: str, value: str, min_length: int = 6) -> bool:
    normalized = _compact(value)
    if not normalized or normalized == "未填写":
        return True

    content_normalized = _compact(content)
    if normalized in content_normalized:
        return True

    separators = "，,。.;；:：、!?！？\n"
    chunks = [normalized]
    for separator in separators:
        chunks = [part for chunk in chunks for part in chunk.split(separator)]
    return any(len(chunk) >= min_length and chunk in content_normalized for chunk in chunks)


def check_report_quality(
    content: str,
    expected_confusions: Sequence[str] | None = None,
    main_confusion_text: str | None = None,
    prohibited_personal_values: Sequence[str] | None = None,
    finish_reason: str | None = None,
) -> dict[str, Literal["passed", "warning", "failed"] | list[str]]:
    warnings: list[str] = []

    for section in REQUIRED_SECTIONS:
        if not _has_heading(content, section):
            warnings.append(f"缺少模块：{section}")

    for required in REQUIRED_CONTENT:
        is_subheading = required in {*PLAN_TITLES, "你现在最大的困惑是什么", "这个困惑背后的真正问题是什么", "接下来可以如何验证"}
        if (is_subheading and not _has_subheading(content, required)) or (not is_subheading and required not in content):
            warnings.append(f"缺少关键内容：{required}")

    if finish_reason == "length":
        warnings.append("模型输出因长度限制被截断")

    if expected_confusions:
        missing_confusions = [item for item in expected_confusions if item and item not in content]
        if len(missing_confusions) == len([item for item in expected_confusions if item]):
            warnings.append("缺少当前困惑选项引用")

    if main_confusion_text and not _contains_meaningful_snippet(content, main_confusion_text):
        warnings.append("未明显回应主要困惑描述")

    for phrase in DISCOURAGED_PHRASES:
        if phrase in content:
            warnings.append(f"出现不建议表达：{phrase}")

    for section, length in _section_lengths(content).items():
        limit = SECTION_MAX_LENGTHS[section]
        minimum = SECTION_MIN_LENGTHS[section]
        if length < minimum:
            warnings.append(f"模块内容过少：{section} {length}/{minimum} 字符")
        if length > limit:
            warnings.append(f"模块超过建议上限：{section} {length}/{limit} 字符")

    count = count_chineseish_words(content)
    if count < MIN_REPORT_LENGTH:
        warnings.append(f"报告内容严重不足：{count}/{MIN_REPORT_LENGTH} 字符")
    if count < 4800:
        warnings.append(f"报告长度不足 5000 字符建议范围：{count}")
    if count > 6500:
        warnings.append(f"报告长度超过 6000 字符建议范围：{count}")

    warnings.extend(_plan_warnings(content))

    action_section_start = content.find("四、接下来6个月，你可以做的3—5件事")
    action_section_end = content.find("五、半年后我会问你这些问题")
    if action_section_start >= 0 and action_section_end > action_section_start:
        action_section = content[action_section_start:action_section_end]
        action_count = len(re.findall(r"(?m)^\s*\d+[.、]\s+", action_section))
        if not 3 <= action_count <= 5:
            warnings.append(f"行动项数量不符合3—5项要求：{action_count}")

    if prohibited_personal_values:
        leaked = [
            value.strip()
            for value in prohibited_personal_values
            if isinstance(value, str) and len(value.strip()) >= 3 and value.strip() in content
        ]
        if leaked:
            warnings.append("报告包含不应展示的个人身份信息")
    if contains_obvious_contact_details(content):
        warnings.append("报告包含疑似联系方式或长数字标识")

    status: Literal["passed", "warning", "failed"] = "passed"
    fatal_warnings: list[str] = []
    if warnings:
        failed_markers = [
            "缺少模块",
            "缺少关键内容",
            "模型输出因长度限制被截断",
            "模块内容过少",
            "报告内容严重不足",
            "路径内容过少",
            "路径缺少验证行动或切换条件",
            "路径内容高度重复",
            "行动项数量不符合",
            "报告包含不应展示的个人身份信息",
            "报告包含疑似联系方式或长数字标识",
        ]
        fatal_warnings = [
            item
            for item in warnings
            if any(marker in item for marker in failed_markers)
        ]
        status = "failed" if fatal_warnings else "warning"
    return {"status": status, "warnings": warnings, "fatalWarnings": fatal_warnings}
