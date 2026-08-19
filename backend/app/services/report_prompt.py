import json

from app.schemas.assessment import AssessmentResponse
from app.schemas.profile import CareerProfile
from app.services.profile_prompt import (
    MODEL_EXCLUDED_RESPONSE_FIELDS,
    redact_model_forbidden_values,
)


def _list(items: list[str]) -> str:
    return "、".join(items) if items else "暂未填写"


def build_report_messages(response: AssessmentResponse, profile: CareerProfile) -> list[dict[str, str]]:
    # Work from a redacted model copy so a future prompt edit cannot expose a
    # forbidden response property simply by interpolating it.
    safe_response = response.model_copy(
        update={field_name: None for field_name in MODEL_EXCLUDED_RESPONSE_FIELDS}
    )
    structured_profile = json.dumps(
        {
            "summary": profile.summary,
            "coreMotivations": [item.model_dump() for item in profile.coreMotivations],
            "verifiedStrengths": [item.model_dump() for item in profile.verifiedStrengths],
            "potentialStrengths": [item.model_dump() for item in profile.potentialStrengths],
            "keyRisks": [item.model_dump() for item in profile.keyRisks],
            "visionConsistency": profile.visionConsistency.model_dump() if profile.visionConsistency else None,
            "contradictions": [item.model_dump() for item in profile.contradictions],
            "informationGaps": profile.informationGaps,
            "educationPathAssessments": [item.model_dump() for item in profile.educationPathAssessments],
            "planA": profile.planA.model_dump() if profile.planA else None,
            "planB": profile.planB.model_dump() if profile.planB else None,
            "planC": profile.planC.model_dump() if profile.planC else None,
            "reportEvidenceMap": profile.reportEvidenceMap,
        },
        ensure_ascii=False,
        indent=2,
    )
    structured_profile = redact_model_forbidden_values(structured_profile, response)
    user_content = f"""
请生成约 5000-6000 个中文字符的报告，只包含下面六个主体模块和最后的安全提醒，标题名称与顺序不得改变。各模块必须控制在规定上限内，避免重复问卷答案或展开过多生活细节：

一、你5—10年后的人生画像
二、你的核心优势与风险短板
三、人生愿景与当前路径的匹配度诊断
四、接下来6个月，你可以做的3—5件事
五、半年后我会问你这些问题
六、一个值得你长期思考的问题
安全提醒

各模块写作要求：

一、你5—10年后的人生画像（建议600—750字，最多850字）
依据基本信息、5年愿景、10年愿景和价值观，概括城市、行业与岗位、生活状态和核心技能。只保留最能体现人生方向的内容，不逐项复述问卷，不展开收入、住房、家庭和爱好的琐碎细节。

二、你的核心优势与风险短板（建议750—900字，最多1050字）
结合能力自评、兴趣倾向、行动基础、现有准备、资源缺口和健康精力，提炼且仅提炼2项核心优势和2项关键风险。分别使用“核心优势：”和“风险短板：”作为加粗小标题；每组编号都从1开始。每项写清表现、成因，以及对升学、就业和长期规划的影响。不要贴固定人格标签。

三、人生愿景与当前路径的匹配度诊断（建议1500—1800字，最多2000字，报告重点）
对照学历阶段、升学/就业/出国/体制内/企业研发等路径、专业背景、学业竞争力和5—10年愿景，判断当前路径与目标城市、行业、岗位和生活安排的匹配度，明确现实偏差。
本模块开头必须固定回应学生最大困惑，依次使用三个独立小标题：
“你现在最大的困惑是什么？”
“这个困惑背后的真正问题是什么？”
“接下来可以如何验证？”
这三段必须引用学生选择的careerConfusions，并回应mainConfusionText；如果mainConfusionText未填写，也必须根据已选困惑说明当前最需要验证的问题，不允许只泛泛鼓励。
在“你现在最大的困惑是什么？”下面必须原文写出一句：“当前选择的困惑包括：{_list(safe_response.careerConfusions)}。”，然后再解释含义。
随后必须提出“Plan A：主攻路径”“Plan B：备选路径”和“Plan C：系统建议路径”。Plan A和Plan B必须沿用结构化画像给出的方向，只能补充表达和执行细节；Plan C必须跳出学生原有设定，基于系统识别的优势、兴趣、限制和风险给出第三条值得探索的路径，不能重复Plan A或Plan B。分别说明路径内容、适配依据、目标行业和城市契合度、进入难度、主要收益、机会成本和切换条件，最后给出清晰但不绝对的当前建议。
“Plan A：主攻路径”“Plan B：备选路径”和“Plan C：系统建议路径”必须分别作为独立小标题；三组下面的编号都必须各自从1开始。

四、接下来6个月，你可以做的3—5件事（建议1050—1300字，最多1450字）
由长期愿景倒推3—5项具体行动。每项行动标题使用一级编号；该行动下的“做什么、为什么做、对Plan A的帮助、如何为Plan B预留后手、如何验证Plan C、完成标准、建议时间”使用无序列表，不得继续使用与行动标题同级的数字编号。覆盖学业、技能、项目或实习、信息调研、自我提升、健康管理中最相关的事项，不要泛泛而谈。

五、半年后我会问你这些问题（建议350—450字，最多550字）
给出5—7个可复盘的问题，覆盖行动完成度、行业岗位认知、核心困惑和Plan A/Plan B/Plan C是否需要切换。问题要能根据事实简短回答，不为每个问题附加长篇解释。

六、一个值得你长期思考的问题（建议220—320字，最多380字）
用一小段文字指出问题与学生的关系，再给出一句开放式问题。紧扣其最大困惑、理想与现实落差或双路径取舍，不重复前文。

安全提醒
固定提醒学生：报告是生涯探索参考，不是医学、心理诊断或人生定论；如持续感到焦虑、低落或无力，应联系学校心理咨询中心；升学就业的具体政策与机会应向学校就业指导中心、教务部门或官方渠道核实。

格式要求：
- 使用 Markdown 标题：报告标题用“#”，六个模块及安全提醒用“##”。
- “你现在最大的困惑是什么？”“这个困惑背后的真正问题是什么？”“接下来可以如何验证？”和 Plan A / Plan B / Plan C 这六个指定小标题必须使用“###”；其他小标题可以使用“###”或单独一行的“**小标题：**”。只加粗标题、小标题和每条内容开头的短标签，不要加粗正文。
- 编号只用于模块内部的并列项目。每个新的小标题或分组都从1重新开始，禁止跨模块连续编号。
- Plan A、Plan B和Plan C是三个独立分组，各自下面的编号列表必须从1重新开始。
- 第四模块只有3—5个行动标题使用数字编号；每项行动的说明字段必须使用“-”无序列表。
- “安全提醒”必须单独使用“## 安全提醒”标题，不要用“***”等分隔线代替标题。
- 不输出“质量检查”“生成说明”“字数统计”等系统信息。
- 不复述整份问卷，不使用“你一定”“你必须”“唯一选择”等绝对表达。
- 同一事实或建议最多出现一次；优先给出结论、依据和行动，删除铺垫、泛泛鼓励及重复解释。
- 不分析、不预测也不评价薪资、收入区间、收入目标是否现实或购房能力；报告正文不得出现具体薪资判断。
- 不输出直接身份信息。
- 优先使用结构化画像中的结论、证据、反证与置信度。低置信度结论必须使用“可能”“有待验证”等表达。
- 已验证优势和潜在优势必须严格区分；不得把potentialStrengths写成已经具备的成熟能力。
- Plan A和Plan B必须沿用结构化画像给出的方向，只能补充表达和执行细节，不能擅自交换或另造路径。
- Plan C优先沿用结构化画像中的planC；如果planC为空，则只能基于结构化画像的优势、兴趣、限制、风险、信息缺口和脱敏问卷生成低成本验证型建议，不得凭空创造经历或确定结论。
- 画像中指出的信息缺口和矛盾必须转化为验证行动，不得用猜测填补。

学生信息（已按最小必要原则脱敏）：
- 学历阶段：{safe_response.educationStage or "未填写"}
- 年级：{safe_response.grade}
- 专业：{safe_response.collegeMajor}
- 家乡或成长地：{safe_response.hometown or "未填写"}
- 当前困惑：{_list(safe_response.careerConfusions)}；其他困惑={safe_response.careerConfusionOther or "无"}
- 主要困惑描述：{safe_response.mainConfusionText or "未填写"}
- 读硕士意向：{safe_response.mastersIntention}
- 硕士规划：{safe_response.mastersPlan or "未填写"}
- 读博士意向：{safe_response.phdIntention}
- 博士规划：{safe_response.phdPlan or "未填写"}
- 博士后续发展方向：{safe_response.doctoralCareerDirection or "不适用"}；其他方向={safe_response.doctoralCareerOther or "无"}
- 教育路径原因：{_list(safe_response.educationPathReasons)}；其他原因={safe_response.educationPathReasonOther or "无"}
- 五年愿景：城市={safe_response.fiveYearCity}；行业={safe_response.fiveYearIndustry}；岗位/角色={safe_response.fiveYearRole}
- 五年生活：家庭状态={safe_response.fiveYearFamilyStatus}；住房={safe_response.fiveYearHousingPlan}；爱好与核心技能={safe_response.fiveYearHobbiesSkills}
- 十年愿景：城市={safe_response.tenYearCity}；行业={safe_response.tenYearIndustry}；岗位/角色={safe_response.tenYearRole}
- 十年生活：家庭状态={safe_response.tenYearFamilyStatus}；住房={safe_response.tenYearHousingPlan}；爱好与核心技能={safe_response.tenYearHobbiesSkills}
- 价值观前三项：{_list(safe_response.topValuesRanked)}
- 能力自评：逻辑={safe_response.abilityScores.logic}/5；表达={safe_response.abilityScores.expression}/5；空间设计={safe_response.abilityScores.spatialDesign}/5；人际理解={safe_response.abilityScores.interpersonal}/5
- 兴趣倾向：动手={safe_response.interestScores.handsOn}/5；研究={safe_response.interestScores.research}/5；创作={safe_response.interestScores.creation}/5；助人={safe_response.interestScores.helping}/5；领导影响={safe_response.interestScores.leadership}/5；规则细节={safe_response.interestScores.detail}/5
- 学业竞争力：GPA={safe_response.currentGpa or "未填写"} / {safe_response.gpaScale or "未填写"}；排名={safe_response.majorRank or "未填写"} / {safe_response.majorTotal or "未填写"}；挂科重修={safe_response.failedCourseStatus or "未填写"}
- 第二专业：{safe_response.hasSecondMajor or "未填写"}；名称={safe_response.secondMajorName or "未填写"}；程度={safe_response.secondMajorProgress or "未填写"}；职业相关意愿={safe_response.secondMajorCareerInterest or "未填写"}
- 转专业：{safe_response.hasTransferredMajor or "未填写"}；原专业={safe_response.originalMajorName or "未填写"}；原因={safe_response.transferReason or "未填写"}；原专业能力保留={safe_response.originalMajorRetainedSkills or "未填写"}
- 常被称赞的特质：{_list(safe_response.praisedTraits)}
- 特质成果证据：{safe_response.traitEvidence or "未填写"}
- 兴趣探索：沉浸活动={safe_response.immersiveActivities or "未填写"}；喜欢知识={safe_response.favoriteKnowledgeAreas or "未填写"}；无奖励也愿意做={safe_response.selfDrivenActivities or "未填写"}；偏好工作方式={_list(safe_response.preferredWorkStyle)}
- 已有准备：{_list(safe_response.currentPreparations)}；其他准备={safe_response.currentPreparationOther or "无"}
- 准备细节：{safe_response.preparationDetails or "未填写"}
- 缺少资源：{_list(safe_response.missingResources)}
- 专业去向认知：{safe_response.majorOutcomeAwareness}
- 岗位认知：{safe_response.targetJobAwareness}
- 信息渠道：{_list(safe_response.jobInfoChannels)}；其他渠道={safe_response.jobInfoChannelOther or "无"}
- 健康精力：{safe_response.healthEnergyStatus}
- 运动情况：{safe_response.exerciseFrequency or "未填写"}
- 长期坚持能力：{safe_response.longTermPersistence}/5
- 执行力：{safe_response.executionStyle or "未填写"}
- 抗压恢复：失败恢复={safe_response.failureRecoveryTime or "未填写"}；自我怀疑={safe_response.selfDoubtFrequency or "未填写"}；解决问题方式={safe_response.problemSolvingStyle or "未填写"}；需要支持={safe_response.supportNeed or "未填写"}
- 工作承受：高强度经历={safe_response.highIntensityExperience or "未填写"}；事务性工作接受={safe_response.routineWorkTolerance or "未填写"}；职业风险偏好={safe_response.careerRiskPreference or "未填写"}

结构化画像分析：
{structured_profile}
""".strip()
    user_content = redact_model_forbidden_values(user_content, response)

    return [
        {
            "role": "system",
            "content": (
                "你是一名温和、严谨、熟悉高校学生发展规律的生涯规划顾问。"
                "请基于学生的最小必要脱敏问卷和画像生成中文《我的生涯蓝图》。"
                "所有判断都必须能在输入信息中找到依据，不虚构经历，不做人格定论，不制造焦虑。"
                "结构化画像已经完成分析判断，你负责依据画像证据写作，不得绕过证据重新发明结论。"
                "报告要写实、具体、有分析深度，既指出问题，也给出可执行的三路径方案。"
            ),
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]
