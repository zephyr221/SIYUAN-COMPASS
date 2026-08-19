import { useState } from "react";
import { Link } from "react-router-dom";
import { deleteMyBusinessData } from "../api/privacy";
import { useAuth } from "../auth/AuthContext";
import { clearAssessmentLocalData } from "../storage/assessmentStorage";

export function PrivacyPage() {
  const { user } = useAuth();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function clearMyData() {
    if (!user || user.role !== "student") return;
    const confirmed = window.confirm(
      "确定清除当前账号的全部业务数据吗？\n\n"
      + "这会永久删除未提交草稿、问卷、用户画像、报告、历史版本、反馈和生成任务，无法撤销；"
      + "登录账号、当日报告生成次数和语音转写次数计数会保留，计数会在自然日结束后清零。"
    );
    if (!confirmed) return;

    setDeleting(true);
    setError("");
    setSuccess("");
    try {
      const result = await deleteMyBusinessData();
      clearAssessmentLocalData(user.id);
      setSuccess(result.message || "你的业务数据已清除。");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "数据清除失败，请稍后重试。");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <main className="shell page privacy-page">
      <div className="page-title">
        <h1>隐私政策与数据管理</h1>
        <p>了解系统会处理哪些数据、用于什么目的，以及你如何管理自己的数据。</p>
      </div>

      <section className="panel privacy-section">
        <h2>我们处理的信息</h2>
        <ul>
          <li><strong>认证信息：</strong>由登录认证提供的账号标识、显示名和角色，用于身份确认、数据归属和权限判断。</li>
          <li><strong>问卷信息：</strong>教育背景、学业情况、职业意向、价值偏好、能力兴趣、行动准备及身心状态自评。</li>
          <li><strong>身份与联系信息：</strong>姓名、学号和联系方式为选填，用于问卷归属、后台必要管理或经你主动提供后的联系；不会发送给 AI 服务。</li>
          <li><strong>必填补充信息：</strong>性别、5 年预期收入和 10 年预期收入为问卷必填项。性别可用于完善生涯路径分析；收入预期只作问卷记录，不用于判断收入是否现实，也不会发送给 AI 服务。</li>
          <li><strong>生成内容：</strong>结构化画像、生涯报告、质量检查结果和你主动提交的反馈。</li>
        </ul>
      </section>

      <section className="panel privacy-section">
        <h2>数据如何使用和保存</h2>
        <ul>
          <li>未提交问卷草稿只属于当前账号，云端默认保留 30 天；浏览器本地另保留 7 天作为网络异常时的兜底。退出或切换账号时会清除当前设备草稿，过期云端草稿由系统自动清理。</li>
          <li>生成报告时，与生涯分析相关的回答会在脱敏后发送给系统配置的 AI 服务；姓名、学号、联系方式、收入预期和内部标识不会发送，自由文本中的明显手机号、邮箱和长数字标识也会替换。</li>
          <li>系统无法可靠识别自由文本中的所有姓名、地址或账号，请不要在问卷自由文本中填写不必要的身份信息。</li>
          <li>已提交的问卷、画像、报告和反馈会保存在系统中，便于你查看结果、修改问卷后生成新报告及改进报告质量；正式创建报告任务后，未提交草稿会自动删除。</li>
          <li>系统只保留当前自然日的生成次数计数用于执行配额；清除业务数据不会重置当日次数，计数会在自然日结束后清零。</li>
          <li>语音录音只在转写请求期间短暂保存在服务内存中，不写入数据库、不进入报告；转写文本只有在你确认并提交问卷后才会随对应问卷字段保存。语音转写按账号限制每日次数。</li>
          <li>报告仅作为生涯探索参考，不是医学、心理诊断或人生定论。</li>
        </ul>
      </section>

      <section className="panel privacy-section privacy-controls">
        <h2>管理你的数据</h2>
        <p>你可以在“我的报告”中单独删除一份报告及关联数据，也可在这里一次清除当前账号的全部业务数据。</p>
        {error && <div className="error">{error}</div>}
        {success && <div className="success" role="status">{success}</div>}
        {user?.role === "student" ? (
          <button className="button danger" disabled={deleting} onClick={clearMyData} type="button">
            {deleting ? "清除中..." : "清除我的全部业务数据"}
          </button>
        ) : !user ? (
          <p><Link className="text-link" to="/login">登录后管理我的数据</Link></p>
        ) : null}
      </section>
    </main>
  );
}
