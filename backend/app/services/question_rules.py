from __future__ import annotations

import json

# These rules are a concise transcription of docs/01-问卷与报告规范.md.
# Do not expand them with additional personality or career assumptions.
QUESTION_RULES: dict[str, dict[str, object]] = {
    "studentName": {
        "purpose": "仅用于报告归属和测试回访，不作为画像判断证据，不在报告正文中展示。",
        "checks": [],
    },
    "studentNumber": {
        "purpose": "仅用于区分同名学生和后台管理，不作为画像判断证据，不在报告正文中展示。",
        "checks": [],
    },
    "contactInfo": {
        "purpose": "仅用于测试回访，不作为画像判断证据，不在报告正文中展示。",
        "checks": [],
    },
    "educationStage": {
        "purpose": "决定年级、升学和就业问题的适用范围，避免本科、硕士、博士被不相关问题干扰。",
        "checks": ["grade", "mastersIntention", "phdIntention", "doctoralCareerDirection"],
    },
    "grade": {
        "purpose": "结合教育路径，测算距离第一次就业的剩余时间，确定实现理想就业的准备周期。",
        "checks": ["educationStage", "mastersIntention", "phdIntention", "doctoralCareerDirection"],
    },
    "gender": {
        "purpose": "制定的生涯规划方案，需要结合性别特征有所调整",
        "checks": [],
    },
    "collegeMajor": {
        "purpose": "了解专业背景，判断如何与就业和生涯目标结合。",
        "checks": ["fiveYearIndustry", "fiveYearRole", "tenYearIndustry", "tenYearRole"],
    },
    "hometown": {
        "purpose": "结合未来5年、10年规划中选择的工作地点分析：距离远近、城市定位差距大小，结合自身规划，判断其就业后的生存难易程度，其性格底色",
        "checks": ["fiveYearCity", "tenYearCity"],
    },
    "mastersIntention": {
        "purpose": "了解是否读研，以及本校、国内其他高校或留学、是否转专业、是否符合条件和准备计划。",
        "checks": ["mastersPlan", "educationPathReasons"],
    },
    "mastersPlan": {
        "purpose": "了解读研方向、条件差距和准备工作，结合拟获取学位给出建议。",
        "checks": ["mastersIntention", "currentPreparations"],
    },
    "phdIntention": {
        "purpose": "了解是否读博，以及本校、国内其他高校或留学、是否转专业、是否符合条件和准备计划。",
        "checks": ["phdPlan", "educationPathReasons"],
    },
    "phdPlan": {
        "purpose": "了解读博方向、条件差距和准备工作，结合拟获取学位给出建议。",
        "checks": ["phdIntention", "currentPreparations"],
    },
    "doctoralCareerDirection": {
        "purpose": "博士生后续发展方向，不再分析读硕或读博，而是判断科研、企业研发、博士后、体制内、创业等路径的适配证据。",
        "checks": ["educationStage", "phdPlan", "doctoralCareerOther", "careerRiskPreference", "highIntensityExperience"],
    },
    "educationPathReasons": {
        "purpose": "分析教育路径原因、在意因素、生涯思考和迷茫点，并与5年、10年规划对应。",
        "checks": ["educationPathReasonOther", "mastersIntention", "phdIntention", "fiveYearIndustry", "fiveYearRole", "tenYearIndustry", "tenYearRole"],
    },
    "fiveYearCity": {
        "purpose": "判断目标城市的宜居程度，以及是否与职业发展方向一致。",
        "checks": ["hometown", "fiveYearIndustry", "fiveYearRole"],
    },
    "fiveYearIncome": {
        "purpose": "该字段只作为原始问卷信息保存，不用于画像分析或职业路径判断。",
        "checks": [],
    },
    "fiveYearIndustry": {
        "purpose": "了解职业发展规划，检查与专业是否匹配；不匹配时检查相关积累。",
        "checks": ["collegeMajor", "currentPreparations"],
    },
    "fiveYearRole": {
        "purpose": "判断个人发展目标是否符合行业规律，并结合现有规划给出建议。",
        "checks": ["fiveYearIndustry", "currentPreparations", "targetJobAwareness"],
    },
    "fiveYearFamilyStatus": {
        "purpose": "了解亲密关系和生活状态偏好，并将其纳入整体生涯规划。",
        "checks": ["fiveYearCity", "fiveYearHousingPlan"],
    },
    "fiveYearHousingPlan": {
        "purpose": "了解居住状态偏好，但不评估购房能力或收入可行性。",
        "checks": ["fiveYearCity"],
    },
    "fiveYearHobbiesSkills": {
        "purpose": "判断爱好和核心技能能否规划为生涯第二曲线。",
        "checks": ["interestScores", "currentPreparations"],
    },
    "tenYearCity": {
        "purpose": "按5年城市问题的同一目的，判断长期城市与职业方向是否一致。",
        "checks": ["hometown", "fiveYearCity", "tenYearIndustry", "tenYearRole"],
    },
    "tenYearIncome": {
        "purpose": "该字段只作为原始问卷信息保存，不用于画像分析或职业路径判断。",
        "checks": [],
    },
    "tenYearIndustry": {
        "purpose": "按5年行业问题的同一目的，检查长期赛道与专业及已有积累是否匹配。",
        "checks": ["collegeMajor", "fiveYearIndustry", "currentPreparations"],
    },
    "tenYearRole": {
        "purpose": "按5年岗位问题的同一目的，判断长期岗位层级是否符合行业规律。",
        "checks": ["fiveYearRole", "tenYearIndustry", "currentPreparations"],
    },
    "tenYearFamilyStatus": {
        "purpose": "按5年生活状态问题的同一目的，将长期家庭生活偏好纳入生涯规划。",
        "checks": ["tenYearCity", "tenYearHousingPlan"],
    },
    "tenYearHousingPlan": {
        "purpose": "了解长期居住状态偏好，但不评估购房能力或收入可行性。",
        "checks": ["tenYearCity", "fiveYearHousingPlan"],
    },
    "tenYearHobbiesSkills": {
        "purpose": "判断长期爱好和核心技能能否形成生涯第二曲线。",
        "checks": ["fiveYearHobbiesSkills", "interestScores", "currentPreparations"],
    },
    "topValuesRanked": {
        "purpose": "了解最在意的价值，检查是否与生涯规划匹配，并辅助判断适合的工作方向。",
        "checks": ["fiveYearRole", "fiveYearFamilyStatus", "tenYearRole"],
    },
    "abilityScores": {
        "purpose": "判断适合的工作类型，以及能力自评是否与自我规划匹配；不匹配时给出建议。",
        "checks": ["fiveYearIndustry", "fiveYearRole", "tenYearRole"],
    },
    "interestScores": {
        "purpose": "判断适合的工作类型，以及兴趣是否与自我规划匹配；不匹配时给出建议。",
        "checks": ["fiveYearIndustry", "fiveYearRole", "tenYearRole"],
    },
    "currentGpa": {
        "purpose": "作为学业竞争力线索，用于判断保研、考研、出国、读博和学术路径可行性；不能脱离满分、排名和经历单独下结论。",
        "checks": ["gpaScale", "majorRank", "majorTotal", "mastersIntention", "phdIntention"],
    },
    "gpaScale": {
        "purpose": "解释GPA分数的量尺，避免误读学业成绩。",
        "checks": ["currentGpa"],
    },
    "majorRank": {
        "purpose": "辅助判断学业竞争力和保研、奖学金、升学竞争基础。",
        "checks": ["majorTotal", "currentGpa"],
    },
    "majorTotal": {
        "purpose": "解释专业排名含义，避免把排名数字孤立解读。",
        "checks": ["majorRank"],
    },
    "failedCourseStatus": {
        "purpose": "识别学业稳定性风险和需要补救的短板，不作道德评价。",
        "checks": ["currentGpa", "majorRank", "healthEnergyStatus", "executionStyle"],
    },
    "hasSecondMajor": {
        "purpose": "识别复合型发展路径和Plan B潜在来源。",
        "checks": ["secondMajorName", "secondMajorProgress", "secondMajorCareerInterest", "fiveYearIndustry"],
    },
    "secondMajorName": {
        "purpose": "了解第二专业方向，判断与主专业、目标行业和备选路径的关联。",
        "checks": ["collegeMajor", "secondMajorProgress", "secondMajorCareerInterest"],
    },
    "secondMajorProgress": {
        "purpose": "判断第二专业是否已有实质投入和成果，不把兴趣等同于能力。",
        "checks": ["secondMajorName", "currentPreparations"],
    },
    "secondMajorCareerInterest": {
        "purpose": "判断第二专业是否可能进入职业路径或仅作为兴趣拓展。",
        "checks": ["secondMajorName", "fiveYearIndustry", "tenYearIndustry"],
    },
    "hasTransferredMajor": {
        "purpose": "识别转专业经历或意愿背后的动机、适应能力和跨专业资源。",
        "checks": ["originalMajorName", "transferReason", "originalMajorRetainedSkills"],
    },
    "originalMajorName": {
        "purpose": "了解原专业背景，判断是否可以成为交叉方向或备选路径。",
        "checks": ["collegeMajor", "originalMajorRetainedSkills", "fiveYearIndustry"],
    },
    "transferReason": {
        "purpose": "分析转专业原因，区分兴趣变化、能力匹配、外部压力或信息不足。",
        "checks": ["topValuesRanked", "careerConfusions", "originalMajorName"],
    },
    "originalMajorRetainedSkills": {
        "purpose": "判断旧专业知识能力是否还能作为备选路径或复合优势。",
        "checks": ["originalMajorName", "secondMajorName", "fiveYearRole"],
    },
    "praisedTraits": {
        "purpose": "收集他人反馈中的潜在优势线索，但必须结合成果证据后才能判定为已验证优势。",
        "checks": ["traitEvidence", "currentPreparations"],
    },
    "traitEvidence": {
        "purpose": "验证被称赞特质是否产生过成果，区分已验证优势和待验证优势。",
        "checks": ["praisedTraits", "currentPreparations"],
    },
    "immersiveActivities": {
        "purpose": "识别稳定兴趣和可能长期投入的活动。",
        "checks": ["interestScores", "fiveYearHobbiesSkills", "selfDrivenActivities"],
    },
    "favoriteKnowledgeAreas": {
        "purpose": "识别主动学习偏好，判断专业、行业和岗位方向是否匹配。",
        "checks": ["collegeMajor", "fiveYearIndustry", "interestScores"],
    },
    "selfDrivenActivities": {
        "purpose": "判断内在动机和无需外部奖励时的行动倾向。",
        "checks": ["immersiveActivities", "executionStyle", "longTermPersistence"],
    },
    "preferredWorkStyle": {
        "purpose": "判断更偏好的工作方式，并与能力、兴趣、目标岗位进行交叉验证。",
        "checks": ["abilityScores", "interestScores", "fiveYearRole"],
    },
    "currentPreparations": {
        "purpose": "基于生涯规划判断执行力，并检查努力方向是否正确。",
        "checks": ["mastersPlan", "phdPlan", "fiveYearIndustry", "fiveYearRole"],
    },
    "preparationDetails": {
        "purpose": "对已做准备进行具体化，验证课程、比赛、科研、项目、证书、作品、实习、社团等是否能支撑目标。",
        "checks": ["currentPreparations", "currentPreparationOther", "targetJobAwareness"],
    },
    "missingResources": {
        "purpose": "判断执行力和当前短板，并给出补齐方向、能力或资源的建议。",
        "checks": ["currentPreparations", "targetJobAwareness"],
    },
    "majorOutcomeAwareness": {
        "purpose": "辅助判断执行力、社交能力和信息索取能力。",
        "checks": ["jobInfoChannels", "currentPreparations"],
    },
    "targetJobAwareness": {
        "purpose": "判断岗位信息获取能力和执行力。",
        "checks": ["fiveYearRole", "jobInfoChannels", "currentPreparations"],
    },
    "jobInfoChannels": {
        "purpose": "了解信息渠道，给出需要补充的渠道建议，并作为了解行为特点的线索。",
        "checks": ["majorOutcomeAwareness", "targetJobAwareness", "jobInfoChannelOther"],
    },
    "healthEnergyStatus": {
        "purpose": "判断健康管理习惯和精力能否支撑生涯规划需求。",
        "checks": ["exerciseFrequency", "currentPreparations"],
    },
    "exerciseFrequency": {
        "purpose": "判断健康管理习惯能否支撑规划，并考虑将运动偏好结合进建议。",
        "checks": ["healthEnergyStatus"],
    },
    "longTermPersistence": {
        "purpose": "判断长期目标在缺少监督和短期反馈时的坚持能力。",
        "checks": ["executionStyle", "currentPreparations"],
    },
    "executionStyle": {
        "purpose": "判断执行力和启动难度。",
        "checks": ["currentPreparations", "missingResources"],
    },
    "failureRecoveryTime": {
        "purpose": "判断挫折恢复速度和路径风险承受能力，不作心理诊断。",
        "checks": ["selfDoubtFrequency", "problemSolvingStyle", "supportNeed"],
    },
    "selfDoubtFrequency": {
        "purpose": "识别自我怀疑对行动的影响，不作心理诊断。",
        "checks": ["failureRecoveryTime", "problemSolvingStyle", "supportNeed"],
    },
    "problemSolvingStyle": {
        "purpose": "判断遇到问题时是主动解决、观察后行动、依赖外部推动还是回避。",
        "checks": ["executionStyle", "missingResources", "supportNeed"],
    },
    "supportNeed": {
        "purpose": "判断恢复和推进目标时需要的外部支持类型。",
        "checks": ["problemSolvingStyle", "jobInfoChannels"],
    },
    "highIntensityExperience": {
        "purpose": "判断高强度投入承受能力，辅助判断科研、考研、求职、企业研发等路径节奏适配。",
        "checks": ["healthEnergyStatus", "executionStyle", "careerRiskPreference"],
    },
    "routineWorkTolerance": {
        "purpose": "判断对事务性、重复性、细节型工作的接受程度，辅助判断体制内、运营、行政、科研辅助等路径适配。",
        "checks": ["interestScores", "preferredWorkStyle", "careerRiskPreference"],
    },
    "careerRiskPreference": {
        "purpose": "判断对稳定、市场风险和自主性之间的取舍，辅助选择体制内、企业、创业或自由职业路径。",
        "checks": ["topValuesRanked", "fiveYearFamilyStatus", "routineWorkTolerance", "highIntensityExperience"],
    },
    "careerConfusions": {
        "purpose": "确定报告重点回答的问题，并按所选困惑分析原因和给出建议。",
        "checks": ["careerConfusionOther", "mainConfusionText"],
    },
    "mainConfusionText": {
        "purpose": "补充学生最核心的困惑，作为报告重点和长期思考问题的依据。",
        "checks": ["careerConfusions"],
    },
}

CAREER_CONFUSION_RULES: dict[str, dict[str, str]] = {
    "不知道未来适合做什么": {
        "purpose": "分析是否对专业兴趣不足，以及是否缺少对自身和职业的了解。",
        "advice": "先了解能力、兴趣和专业出路，再通过实际行动验证。",
    },
    "纠结就业、读研、出国、读博": {
        "purpose": "说明各选择的目的、优缺点、难度及对生涯规划的影响。",
        "advice": "进行综合比较，形成Plan A、Plan B和切换条件。",
    },
    "不确定自己适合哪个行业": {
        "purpose": "分析对性格、能力、生涯规划和本专业行业出路的了解。",
        "advice": "先了解自身和本专业行业；不满足规划时再寻找交叉方向，并咨询本院校友。",
    },
    "不知道本专业未来有哪些出路": {
        "purpose": "分析专业出口的信息缺口。",
        "advice": "通过学长学姐、老师、AI、招聘会HR、实习和校友咨询了解工作并寻找兴趣点。",
    },
    "想提高求职 / 实习竞争力": {
        "purpose": "判断就业目标是否明确。",
        "advice": "明确目标岗位后有针对性地提高。",
    },
    "对未来收入、城市、生活状态感到焦虑": {
        "purpose": "区分焦虑来自经济、人际、工作生活节奏或其他压力。",
        "advice": "针对压力来源提高抗风险能力或调整预期。",
    },
    "家庭期待和个人想法不一致": {
        "purpose": "了解具体冲突，判断是家庭关系问题还是个人方案不够落地。",
        "advice": "根据具体冲突提出沟通、验证和现实调整建议。",
    },
    "想要更清楚地规划未来5—10年": {
        "purpose": "基于学生现有的5年、10年规划进行分析。",
        "advice": "从现有长期愿景倒推路径和行动，不替学生重新设定愿景。",
    },
}


def render_question_rules(selected_confusions: list[str]) -> str:
    selected_rules = {
        item: CAREER_CONFUSION_RULES[item]
        for item in selected_confusions
        if item in CAREER_CONFUSION_RULES
    }
    return json.dumps(
        {
            "source": "docs/01-问卷与报告规范.md",
            "questionRules": QUESTION_RULES,
            "selectedCareerConfusionRules": selected_rules,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
