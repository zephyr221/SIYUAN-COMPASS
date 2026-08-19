from app.schemas.assessment import AssessmentResponseInput

REQUIRED_STRING_FIELDS = {
    "educationStage": "请选择学历阶段",
    "grade": "请选择年级",
    "gender": "请选择性别",
    "collegeMajor": "请填写学院和专业",
    "hometown": "请填写家乡或主要成长地",
    "fiveYearCity": "请填写5年后希望生活或工作的城市",
    "fiveYearIncome": "请填写5年后预期收入",
    "fiveYearIndustry": "请填写5年后希望进入或深耕的行业领域",
    "fiveYearRole": "请填写5年后希望从事的岗位或角色",
    "fiveYearFamilyStatus": "请选择5年后的家庭或亲密关系状态",
    "fiveYearHousingPlan": "请填写5年后的居住或住房状态",
    "fiveYearHobbiesSkills": "请填写5年后希望保留的爱好或核心技能",
    "tenYearCity": "请填写10年后希望生活或工作的城市",
    "tenYearIncome": "请填写10年后预期收入",
    "tenYearIndustry": "请填写10年后希望进入或深耕的行业领域",
    "tenYearRole": "请填写10年后希望从事的岗位或角色",
    "tenYearFamilyStatus": "请选择10年后的家庭或亲密关系状态",
    "tenYearHousingPlan": "请填写10年后的居住或住房状态",
    "tenYearHobbiesSkills": "请填写10年后希望保留的爱好或核心技能",
    "majorOutcomeAwareness": "请选择是否了解本专业毕业生去向",
    "targetJobAwareness": "请选择是否了解心仪岗位要求",
    "healthEnergyStatus": "请选择身体健康和精力状态",
    "failedCourseStatus": "请选择是否有挂科或重修经历",
    "hasSecondMajor": "请选择是否修读第二专业",
    "hasTransferredMajor": "请选择是否有转专业经历",
    "traitEvidence": "请填写特质相关成果",
    "immersiveActivities": "请填写能让你长时间沉浸的事情",
    "favoriteKnowledgeAreas": "请填写喜欢学习的知识领域",
    "selfDrivenActivities": "请填写无外部奖励也愿意完成的事情",
    "currentGpa": "请填写当前 GPA",
    "gpaScale": "请填写 GPA 满分",
    "majorRank": "请填写专业排名",
    "majorTotal": "请填写专业总人数",
    "preparationDetails": "请具体展开说说已做的准备",
    "executionStyle": "请选择执行力自评",
    "failureRecoveryTime": "请选择失败后的恢复速度",
    "selfDoubtFrequency": "请选择自我怀疑情况",
    "problemSolvingStyle": "请选择面对问题时的处理方式",
    "supportNeed": "请选择恢复时需要的支持",
    "highIntensityExperience": "请选择高强度投入经历",
    "routineWorkTolerance": "请选择事务性工作的接受程度",
    "careerRiskPreference": "请选择职业风险偏好",
}


def _has_text(value: object) -> bool:
    return isinstance(value, str) and len(value.strip()) > 0


def _has_array(value: object, minimum: int = 1) -> bool:
    return isinstance(value, list) and len(value) >= minimum


def validate_assessment_fields(input_data: AssessmentResponseInput) -> dict[str, str]:
    data = input_data.model_dump()
    errors: dict[str, str] = {}

    for field, message in REQUIRED_STRING_FIELDS.items():
        if not _has_text(data.get(field)):
            errors[field] = message

    if input_data.educationStage not in {"本科", "硕士", "博士"}:
        errors["educationStage"] = "请选择学历阶段"

    if input_data.educationStage == "本科" and not _has_text(input_data.mastersIntention):
        errors["mastersIntention"] = "请选择本科毕业后的主要计划"
    if input_data.educationStage == "硕士" and not _has_text(input_data.phdIntention):
        errors["phdIntention"] = "请选择硕士毕业后的主要考虑"
    if input_data.educationStage == "博士" and not _has_text(input_data.doctoralCareerDirection):
        errors["doctoralCareerDirection"] = "请选择博士阶段后的发展方向"
    if input_data.doctoralCareerDirection == "其他发展方向" and not _has_text(input_data.doctoralCareerOther):
        errors["doctoralCareerOther"] = "请填写其他发展方向"

    if not _has_array(input_data.educationPathReasons):
        errors["educationPathReasons"] = "请至少选择1项教育路径原因"
    if len(input_data.educationPathReasons) > 3:
        errors["educationPathReasons"] = "教育路径原因最多选择3项"
    if "其他" in input_data.educationPathReasons and not _has_text(input_data.educationPathReasonOther):
        errors["educationPathReasonOther"] = "请填写其他教育路径原因"
    if len(input_data.topValuesRanked) != 3:
        errors["topValuesRanked"] = "请选出最看重的3项价值观"
    if not _has_array(input_data.praisedTraits):
        errors["praisedTraits"] = "请至少选择1项常被称赞的特质"
    if len(input_data.praisedTraits) > 4:
        errors["praisedTraits"] = "常被称赞的特质最多选择4项"
    if not _has_array(input_data.preferredWorkStyle):
        errors["preferredWorkStyle"] = "请至少选择1项更偏好的工作方式"
    if len(input_data.preferredWorkStyle) > 2:
        errors["preferredWorkStyle"] = "偏好工作方式最多选择2项"
    if not _has_array(input_data.currentPreparations):
        errors["currentPreparations"] = "请至少选择1项已做准备"
    if "其他" in input_data.currentPreparations and not _has_text(input_data.currentPreparationOther):
        errors["currentPreparationOther"] = "请填写其他已做准备"
    if not _has_array(input_data.missingResources):
        errors["missingResources"] = "请至少选择1项目前最缺的资源"
    if len(input_data.missingResources) > 3:
        errors["missingResources"] = "目前最缺的资源最多选择3项"
    if not _has_array(input_data.jobInfoChannels):
        errors["jobInfoChannels"] = "请至少选择1个职业或招聘信息渠道"
    if "其他" in input_data.jobInfoChannels and not _has_text(input_data.jobInfoChannelOther):
        errors["jobInfoChannelOther"] = "请填写其他职业信息渠道"
    if not _has_array(input_data.careerConfusions):
        errors["careerConfusions"] = "请至少选择1项当前生涯困惑"
    if len(input_data.careerConfusions) > 3:
        errors["careerConfusions"] = "当前生涯困惑最多选择3项"
    if "其他" in input_data.careerConfusions and not _has_text(input_data.careerConfusionOther):
        errors["careerConfusionOther"] = "请填写其他生涯困惑"

    return errors


def validate_assessment(input_data: AssessmentResponseInput) -> list[str]:
    return list(validate_assessment_fields(input_data).values())
