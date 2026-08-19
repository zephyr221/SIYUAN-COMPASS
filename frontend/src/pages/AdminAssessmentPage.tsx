import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchAdminAssessment } from "../api/admin";
import type { AssessmentResponse } from "../types/assessment";

type FieldSpec = {
  label: string;
  value: (assessment: AssessmentResponse) => unknown;
};

type SectionSpec = {
  title: string;
  fields: FieldSpec[];
};

function formatValue(value: unknown) {
  if (Array.isArray(value)) {
    return value.length > 0 ? value.join(" / ") : "未填写";
  }
  if (typeof value === "number") {
    return String(value);
  }
  if (typeof value === "string") {
    return value.trim() || "未填写";
  }
  return "未填写";
}

function abilityText(assessment: AssessmentResponse) {
  const scores = assessment.abilityScores;
  return `逻辑 ${scores.logic} / 表达 ${scores.expression} / 空间设计 ${scores.spatialDesign} / 人际协作 ${scores.interpersonal}`;
}

function interestText(assessment: AssessmentResponse) {
  const scores = assessment.interestScores;
  return `动手 ${scores.handsOn} / 研究 ${scores.research} / 创造 ${scores.creation} / 助人 ${scores.helping} / 领导 ${scores.leadership} / 细节 ${scores.detail}`;
}

const sections: SectionSpec[] = [
  {
    title: "基本信息",
    fields: [
      { label: "姓名", value: (item) => item.studentName },
      { label: "学号", value: (item) => item.studentNumber },
      { label: "联系方式", value: (item) => item.contactInfo },
      { label: "学历阶段", value: (item) => item.educationStage },
      { label: "年级", value: (item) => item.grade },
      { label: "性别", value: (item) => item.gender },
      { label: "学院 / 专业", value: (item) => item.collegeMajor },
      { label: "家乡", value: (item) => item.hometown },
      { label: "提交时间", value: (item) => new Date(item.submittedAt).toLocaleString("zh-CN") }
    ]
  },
  {
    title: "教育路径",
    fields: [
      { label: "本科毕业计划", value: (item) => item.mastersIntention },
      { label: "考研 / 读研计划", value: (item) => item.mastersPlan },
      { label: "硕士毕业考虑", value: (item) => item.phdIntention },
      { label: "读博计划", value: (item) => item.phdPlan },
      { label: "博士后发展方向", value: (item) => item.doctoralCareerDirection },
      { label: "其他博士发展方向", value: (item) => item.doctoralCareerOther },
      { label: "教育路径原因", value: (item) => item.educationPathReasons },
      { label: "其他教育路径原因", value: (item) => item.educationPathReasonOther }
    ]
  },
  {
    title: "未来愿景",
    fields: [
      { label: "5年后城市", value: (item) => item.fiveYearCity },
      { label: "5年后预期收入", value: (item) => item.fiveYearIncome },
      { label: "5年后行业", value: (item) => item.fiveYearIndustry },
      { label: "5年后岗位", value: (item) => item.fiveYearRole },
      { label: "5年后家庭状态", value: (item) => item.fiveYearFamilyStatus },
      { label: "5年后居住计划", value: (item) => item.fiveYearHousingPlan },
      { label: "5年后爱好 / 技能", value: (item) => item.fiveYearHobbiesSkills },
      { label: "10年后城市", value: (item) => item.tenYearCity },
      { label: "10年后预期收入", value: (item) => item.tenYearIncome },
      { label: "10年后行业", value: (item) => item.tenYearIndustry },
      { label: "10年后岗位", value: (item) => item.tenYearRole },
      { label: "10年后家庭状态", value: (item) => item.tenYearFamilyStatus },
      { label: "10年后居住计划", value: (item) => item.tenYearHousingPlan },
      { label: "10年后爱好 / 技能", value: (item) => item.tenYearHobbiesSkills }
    ]
  },
  {
    title: "价值、能力与兴趣",
    fields: [
      { label: "最看重的价值观", value: (item) => item.topValuesRanked },
      { label: "能力自评", value: abilityText },
      { label: "兴趣自评", value: interestText },
      { label: "常被称赞的特质", value: (item) => item.praisedTraits },
      { label: "特质证据", value: (item) => item.traitEvidence },
      { label: "沉浸活动", value: (item) => item.immersiveActivities },
      { label: "喜欢的知识领域", value: (item) => item.favoriteKnowledgeAreas },
      { label: "自驱活动", value: (item) => item.selfDrivenActivities },
      { label: "偏好工作方式", value: (item) => item.preferredWorkStyle }
    ]
  },
  {
    title: "学业与经历",
    fields: [
      { label: "GPA", value: (item) => [item.currentGpa, item.gpaScale].filter(Boolean).join(" / ") },
      { label: "专业排名", value: (item) => [item.majorRank, item.majorTotal].filter(Boolean).join(" / ") },
      { label: "挂科或重修", value: (item) => item.failedCourseStatus },
      { label: "第二专业", value: (item) => item.hasSecondMajor },
      { label: "第二专业名称", value: (item) => item.secondMajorName },
      { label: "第二专业进度", value: (item) => item.secondMajorProgress },
      { label: "第二专业兴趣", value: (item) => item.secondMajorCareerInterest },
      { label: "转专业经历", value: (item) => item.hasTransferredMajor },
      { label: "原专业", value: (item) => item.originalMajorName },
      { label: "转专业原因", value: (item) => item.transferReason },
      { label: "原专业保留能力", value: (item) => item.originalMajorRetainedSkills },
      { label: "当前准备", value: (item) => item.currentPreparations },
      { label: "其他已做准备", value: (item) => item.currentPreparationOther },
      { label: "准备详情", value: (item) => item.preparationDetails }
    ]
  },
  {
    title: "职业认知与资源",
    fields: [
      { label: "目前最缺资源", value: (item) => item.missingResources },
      { label: "本专业去向了解", value: (item) => item.majorOutcomeAwareness },
      { label: "目标岗位了解", value: (item) => item.targetJobAwareness },
      { label: "信息渠道", value: (item) => item.jobInfoChannels },
      { label: "其他信息渠道", value: (item) => item.jobInfoChannelOther }
    ]
  },
  {
    title: "行动与承压",
    fields: [
      { label: "健康与精力", value: (item) => item.healthEnergyStatus },
      { label: "运动频率", value: (item) => item.exerciseFrequency },
      { label: "长期坚持度", value: (item) => `${item.longTermPersistence} / 5` },
      { label: "执行风格", value: (item) => item.executionStyle },
      { label: "失败恢复时间", value: (item) => item.failureRecoveryTime },
      { label: "自我怀疑频率", value: (item) => item.selfDoubtFrequency },
      { label: "问题解决方式", value: (item) => item.problemSolvingStyle },
      { label: "支持需要", value: (item) => item.supportNeed },
      { label: "高强度经历", value: (item) => item.highIntensityExperience },
      { label: "重复工作耐受", value: (item) => item.routineWorkTolerance },
      { label: "职业风险偏好", value: (item) => item.careerRiskPreference }
    ]
  },
  {
    title: "核心困惑",
    fields: [
      { label: "当前生涯困惑", value: (item) => item.careerConfusions },
      { label: "其他生涯困惑", value: (item) => item.careerConfusionOther },
      { label: "一句话困惑", value: (item) => item.mainConfusionText }
    ]
  }
];

export function AdminAssessmentPage() {
  const { responseId } = useParams();
  const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!responseId) return;
    fetchAdminAssessment(responseId)
      .then(setAssessment)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "问卷加载失败。"));
  }, [responseId]);

  if (error) {
    return <main className="shell page"><div className="error">{error}</div></main>;
  }

  if (!assessment) {
    return <main className="shell page"><div className="panel">问卷加载中...</div></main>;
  }

  return (
    <main className="shell page">
      <div className="page-title">
        <h1>学生问卷内容</h1>
        <p>问卷记录 · {assessment.educationStage || "-"} {assessment.grade || "-"}</p>
      </div>

      <section className="assessment-reader">
        {sections.map((section) => (
          <article className="panel assessment-section" key={section.title}>
            <h2>{section.title}</h2>
            <div className="assessment-field-grid">
              {section.fields.map((field) => (
                <div className="assessment-field" key={field.label}>
                  <span>{field.label}</span>
                  <p>{formatValue(field.value(assessment))}</p>
                </div>
              ))}
            </div>
          </article>
        ))}
      </section>

      <div className="actions">
        <Link className="button secondary" to="/admin">返回后台</Link>
      </div>
    </main>
  );
}
