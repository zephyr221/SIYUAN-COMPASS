import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchAdminAuditLogs, fetchAdminMetrics, fetchAdminRecords } from "../api/admin";
import type { AdminAuditLog } from "../api/admin";
import type { AdminMetrics, AdminRecord, ReportFeedbackRecord } from "../types/report";

const recordsPerPage = 8;

function reportStatusText(record: AdminRecord) {
  if (record.report.qualityStatus === "failed") return "需检查";
  if (record.report.qualityStatus === "warning") return "有提醒";
  if (record.report.qualityStatus === "passed") return "已通过";
  return "未检查";
}

function reportStatusClass(record: AdminRecord) {
  if (record.report.qualityStatus === "failed") return "failed";
  if (record.report.qualityStatus === "warning") return "warning";
  if (record.report.qualityStatus === "passed") return "success";
  return "queued";
}

function averageFeedbackScore(feedback: ReportFeedbackRecord) {
  const total = feedback.understandingScore + feedback.insightScore + feedback.actionScore + feedback.recommendScore;
  return (total / 4).toFixed(1);
}

function compactWarningText(warning: string) {
  const moduleMatch = warning.match(/^模块超过建议上限：(.+?)\s+(\d+)\/(\d+)\s*字符$/);
  if (moduleMatch) {
    return `${moduleMatch[1]}：字数超出（${moduleMatch[2]}/${moduleMatch[3]}）`;
  }

  const reportTooLongMatch = warning.match(/^报告长度超过\s*\d+\s*字符建议范围：(\d+)$/);
  if (reportTooLongMatch) {
    return `报告总长度：字数超出（${reportTooLongMatch[1]}）`;
  }

  const reportTooShortMatch = warning.match(/^报告长度不足\s*\d+\s*字符建议范围：(\d+)$/);
  if (reportTooShortMatch) {
    return `报告总长度：字数不足（${reportTooShortMatch[1]}）`;
  }

  return warning;
}

function reportWarnings(record: AdminRecord) {
  return (record.report.errorMessage || "")
    .split(/[；;]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map(compactWarningText);
}

const auditActionLabels: Record<string, string> = {
  "admin.metrics.read": "查看统计指标",
  "admin.records.read": "查看学生记录",
  "admin.audit.read": "查看审计日志",
  "assessment.read": "查看完整问卷",
  "report.read": "查看报告",
  "report.update": "修改报告",
  "report.delete": "删除报告"
};

export function AdminPage() {
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [records, setRecords] = useState<AdminRecord[]>([]);
  const [auditLogs, setAuditLogs] = useState<AdminAuditLog[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [error, setError] = useState("");
  const [keyword, setKeyword] = useState("");
  const [qualityStatus, setQualityStatus] = useState("all");
  const [educationStage, setEducationStage] = useState("all");
  const [collegeMajor, setCollegeMajor] = useState("all");
  const [page, setPage] = useState(1);

  useEffect(() => {
    Promise.all([fetchAdminMetrics(), fetchAdminRecords(), fetchAdminAuditLogs()])
      .then(([nextMetrics, nextRecords, nextAuditLogs]) => {
        setMetrics(nextMetrics);
        setRecords(nextRecords.records);
        setAuditLogs(nextAuditLogs.items);
        setAuditTotal(nextAuditLogs.total);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "后台数据加载失败。"));
  }, []);

  if (error) {
    return <main className="shell page"><div className="error">{error}</div></main>;
  }

  if (!metrics) {
    return <main className="shell page"><div className="panel">后台数据加载中...</div></main>;
  }

  const educationStages = Array.from(new Set(records.map((record) => record.assessment.educationStage).filter(Boolean))).sort();
  const collegeMajors = Array.from(new Set(records.map((record) => record.assessment.collegeMajor).filter(Boolean))).sort();
  const normalizedKeyword = keyword.trim().toLowerCase();
  const filteredRecords = records.filter((record) => {
    const searchableText = [
      record.student.displayName,
      record.student.username,
      record.assessment.collegeMajor,
    ].filter(Boolean).join(" ").toLowerCase();
    return (
      (!normalizedKeyword || searchableText.includes(normalizedKeyword))
      && (qualityStatus === "all" || record.report.qualityStatus === qualityStatus)
      && (educationStage === "all" || record.assessment.educationStage === educationStage)
      && (collegeMajor === "all" || record.assessment.collegeMajor === collegeMajor)
    );
  });
  const totalPages = Math.max(1, Math.ceil(filteredRecords.length / recordsPerPage));
  const currentPage = Math.min(page, totalPages);
  const displayedRecords = filteredRecords.slice((currentPage - 1) * recordsPerPage, currentPage * recordsPerPage);

  function resetPage(setter: (value: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  function jumpToReport(reportId: string) {
    const recordIndex = records.findIndex((record) => record.report.id === reportId);
    if (recordIndex < 0) return;
    setKeyword("");
    setQualityStatus("all");
    setEducationStage("all");
    setCollegeMajor("all");
    setPage(Math.floor(recordIndex / recordsPerPage) + 1);
    window.setTimeout(() => document.getElementById(`report-${reportId}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }

  return (
    <main className="shell page">
      <div className="page-title">
        <h1>管理员后台</h1>
        <p>查看学生生成记录，并对报告内容进行人工修订。</p>
      </div>
      <section className="metrics">
        <div className="panel stat"><strong>{metrics.assessmentCount}</strong><span>填写记录</span></div>
        <div className="panel stat"><strong>{metrics.reportSuccessCount}</strong><span>成功报告</span></div>
        <div className="panel stat"><strong>{metrics.feedbackCount}</strong><span>反馈数量</span></div>
        <div className="panel stat"><strong>{metrics.reportFailedCount}</strong><span>失败报告</span></div>
      </section>

      <section className="panel admin-score-panel">
        <div className="admin-section-head">
          <div>
            <h2>报告评分</h2>
            <p className="hint">四项平均分来自学生提交的报告反馈。</p>
          </div>
          <span>{metrics.feedbackCount} 份反馈</span>
        </div>
        <div className="score-metrics">
          <div><strong>{metrics.averageUnderstandingScore}</strong><span>平均理解度</span></div>
          <div><strong>{metrics.averageInsightScore}</strong><span>平均启发度</span></div>
          <div><strong>{metrics.averageActionScore}</strong><span>平均行动性</span></div>
          <div><strong>{metrics.averageRecommendScore}</strong><span>平均推荐度</span></div>
        </div>
        <div className="low-score-reports">
          <h3>低分报告列表</h3>
          {metrics.lowScoreReports.length === 0 ? (
            <p className="hint">暂无任一评分低于或等于 2 分的报告。</p>
          ) : (
            <div className="low-score-list">
              {metrics.lowScoreReports.map((reportId) => (
                <button className="low-score-link" key={reportId} onClick={() => jumpToReport(reportId)}>报告 {reportId.slice(0, 8)}</button>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="admin-records">
        <div className="admin-section-head">
          <div>
            <h2>学生生成记录</h2>
            <p className="hint">每条记录包含问卷入口、报告状态和学生反馈。可按学生、状态和问卷信息检索。</p>
          </div>
          <span>{filteredRecords.length} / {records.length} 条</span>
        </div>
        <div className="admin-record-filters" aria-label="生成记录筛选">
          <label className="admin-filter-keyword">
            <span>搜索学生</span>
            <input
              value={keyword}
              onChange={(event) => resetPage(setKeyword, event.target.value)}
              placeholder="姓名、用户名、专业"
            />
          </label>
          <label>
            <span>报告状态</span>
            <select value={qualityStatus} onChange={(event) => resetPage(setQualityStatus, event.target.value)}>
              <option value="all">全部</option>
              <option value="passed">已通过</option>
              <option value="warning">有提醒</option>
              <option value="failed">需检查</option>
              <option value="unchecked">未检查</option>
            </select>
          </label>
          <label>
            <span>教育阶段</span>
            <select value={educationStage} onChange={(event) => resetPage(setEducationStage, event.target.value)}>
              <option value="all">全部</option>
              {educationStages.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label>
            <span>专业</span>
            <select value={collegeMajor} onChange={(event) => resetPage(setCollegeMajor, event.target.value)}>
              <option value="all">全部</option>
              {collegeMajors.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
        </div>
        {records.length === 0 ? (
          <div className="panel empty-state">
            <p>暂无报告记录。</p>
          </div>
        ) : filteredRecords.length === 0 ? (
          <div className="panel empty-state">
            <p>没有符合当前筛选条件的生成记录。</p>
          </div>
        ) : (
          <>
            <div className="admin-record-list">
            {displayedRecords.map((record) => {
              const feedbacks = record.feedbacks ?? [];
              const warnings = reportWarnings(record);
              return (
                <article className="panel admin-record-card" id={`report-${record.report.id}`} key={record.report.id}>
                  <div className="admin-record-top">
                    <div>
                      <div className="admin-record-title">
                        <h3>{record.report.title}</h3>
                        <span className={`job-status-pill ${reportStatusClass(record)}`}>{reportStatusText(record)}</span>
                        {record.report.editedAt && <span className="admin-edit-pill">已人工修改</span>}
                      </div>
                      <p className="hint">{new Date(record.assessment.submittedAt).toLocaleString("zh-CN")} · {record.report.wordCount} 字</p>
                    </div>
                    <div className="admin-record-actions">
                      <Link className="button secondary" to={`/reports/${record.report.id}`}>查看</Link>
                      <Link className="button" to={`/admin/reports/${record.report.id}/edit`}>编辑</Link>
                    </div>
                  </div>

                  <div className="admin-record-grid">
                    <div className="admin-record-block">
                      <span className="admin-block-label">学生</span>
                      <strong>{record.student.displayName}</strong>
                      <p>{record.student.username}</p>
                    </div>
                    <div className="admin-record-block">
                      <span className="admin-block-label">问卷内容</span>
                      <strong>{record.assessment.educationStage || "-"} · {record.assessment.grade || "-"}</strong>
                      <p>专业：{record.assessment.collegeMajor || "-"}</p>
                      <Link className="button secondary admin-block-button" to={`/admin/assessments/${record.report.responseId}`}>
                        查看完整问卷
                      </Link>
                    </div>
                    <div className="admin-record-block">
                      <span className="admin-block-label">报告状态</span>
                      <strong>{reportStatusText(record)}</strong>
                      <p>模型：{record.report.modelName || "-"}</p>
                      <p>版本：{record.report.promptVersion || "-"}</p>
                      {warnings.length > 0 && (
                        <details className="admin-warning-details">
                          <summary>查看提醒内容</summary>
                          <ul>
                            {warnings.map((warning) => (
                              <li key={warning}>{warning}</li>
                            ))}
                          </ul>
                        </details>
                      )}
                    </div>
                  </div>

                  <div className="admin-feedback-section">
                    <div className="admin-feedback-head">
                      <strong>反馈记录</strong>
                      <span>{feedbacks.length} 条</span>
                    </div>
                    {feedbacks.length === 0 ? (
                      <p className="hint">这个报告还没有学生反馈。</p>
                    ) : (
                      <div className="admin-feedback-list">
                        {feedbacks.map((feedback) => (
                          <div className="admin-feedback-item" key={feedback.id}>
                            <div className="admin-feedback-item-head">
                              <strong>{averageFeedbackScore(feedback)} 分</strong>
                              <span>{new Date(feedback.createdAt).toLocaleString("zh-CN")}</span>
                            </div>
                            <div className="admin-feedback-scores">
                              <span>理解 {feedback.understandingScore}</span>
                              <span>启发 {feedback.insightScore}</span>
                              <span>行动 {feedback.actionScore}</span>
                              <span>推荐 {feedback.recommendScore}</span>
                            </div>
                            <p>{feedback.comment?.trim() || "未填写文字反馈。"}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
            </div>
            {totalPages > 1 && (
              <nav className="admin-pagination" aria-label="生成记录分页">
                <button className="button secondary" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>上一页</button>
                <span>第 {currentPage} / {totalPages} 页</span>
                <button className="button secondary" disabled={currentPage === totalPages} onClick={() => setPage(currentPage + 1)}>下一页</button>
              </nav>
            )}
          </>
        )}
      </section>

      <section className="panel admin-audit-panel">
        <div className="admin-section-head">
          <div>
            <h2>管理员审计</h2>
            <p className="hint">记录敏感信息查看、报告修改和删除操作，日志默认保留 180 天。</p>
          </div>
          <span>共 {auditTotal} 条</span>
        </div>
        {auditLogs.length === 0 ? (
          <p className="hint">暂无管理员操作记录。</p>
        ) : (
          <div className="admin-audit-list">
            {auditLogs.map((item) => (
              <div className="admin-audit-item" key={item.id}>
                <div>
                  <strong>{auditActionLabels[item.action] || item.action}</strong>
                  <span>{item.adminDisplayName}</span>
                </div>
                <div>
                  <span>{item.targetType} · {item.targetId === "all" ? "全部记录" : item.targetId.slice(0, 12)}</span>
                  <time dateTime={item.createdAt}>{new Date(item.createdAt).toLocaleString("zh-CN")}</time>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
