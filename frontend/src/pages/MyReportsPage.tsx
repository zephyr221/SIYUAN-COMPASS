import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { cancelAssessmentJob, type GenerationJobStatus } from "../api/assessments";
import { deleteReport, fetchMyReports } from "../api/reports";
import { useAuth } from "../auth/AuthContext";
import { saveAssessmentPrefill } from "../storage/assessmentStorage";
import type { CareerBlueprintReport } from "../types/report";

function isActiveJob(job: GenerationJobStatus) {
  return job.status === "queued" || job.status === "running";
}

function jobStatusText(job: GenerationJobStatus) {
  if (job.status === "queued") return "等待生成";
  if (job.status === "running") return "正在生成";
  if (job.status === "failed") return "生成失败";
  if (job.status === "cancelled") return "已取消";
  return "已生成";
}

function jobTime(job: GenerationJobStatus) {
  const value = job.createdAt || job.updatedAt;
  return value ? new Date(value).toLocaleString("zh-CN") : "时间未知";
}

function qualityText(value: CareerBlueprintReport["qualityStatus"]) {
  if (value === "failed") return "需检查";
  return "已生成";
}

function reportSnapshot(report: CareerBlueprintReport) {
  return report.inputSnapshot?.response;
}

export function MyReportsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [reports, setReports] = useState<CareerBlueprintReport[]>([]);
  const [jobs, setJobs] = useState<GenerationJobStatus[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [cancellingJobId, setCancellingJobId] = useState("");
  const [deletingReportId, setDeletingReportId] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    let closed = false;
    let timer: number | undefined;

    async function load() {
      try {
        const data = await fetchMyReports();
        if (closed) return;
        setReports(data.reports);
        setJobs(data.jobs);
        setError("");
        if (data.jobs.some(isActiveJob)) {
          timer = window.setTimeout(load, 3000);
        }
      } catch (caught) {
        if (!closed) {
          setError(caught instanceof Error ? caught.message : "报告加载失败");
        }
      } finally {
        if (!closed) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      closed = true;
      if (timer) window.clearTimeout(timer);
    };
  }, []);

  async function cancelJob(jobId: string) {
    setCancellingJobId(jobId);
    setError("");
    try {
      const cancelled = await cancelAssessmentJob(jobId);
      setJobs((current) => current.map((job) => (job.jobId === jobId ? cancelled : job)));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "取消生成失败");
    } finally {
      setCancellingJobId("");
    }
  }

  const hasHistory = jobs.length > 0 || reports.length > 0;
  const activeCount = jobs.filter(isActiveJob).length;
  const failedCount = jobs.filter((job) => job.status === "failed").length;

  function editFromReport(report: CareerBlueprintReport) {
    const snapshot = reportSnapshot(report);
    if (!snapshot) {
      setError("这份报告缺少原问卷数据，无法恢复修改。");
      return;
    }
    if (!user) {
      setError("登录状态已失效，请重新登录。");
      return;
    }
    saveAssessmentPrefill(user.id, snapshot);
    navigate("/assessment");
  }

  async function removeReport(report: CareerBlueprintReport) {
    const confirmed = window.confirm(
      `确定删除“${report.title}”吗？\n\n`
      + "这会永久删除该报告、版本和反馈；不再被其他报告使用的关联问卷与画像也会删除，且无法撤销。"
    );
    if (!confirmed) return;

    setDeletingReportId(report.id);
    setError("");
    setSuccess("");
    try {
      const result = await deleteReport(report.id);
      const refreshed = await fetchMyReports();
      setReports(refreshed.reports);
      setJobs(refreshed.jobs);
      setSuccess(result.message || "报告及关联数据已删除。");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "报告删除失败。");
    } finally {
      setDeletingReportId("");
    }
  }

  return (
    <main className="shell page">
      <div className="page-title">
        <h1>我的报告</h1>
        <p>查看当前账号的生成进度、失败记录和已生成报告。</p>
      </div>
      {error && <div className="error">{error}</div>}
      {success && <div className="success" role="status">{success}</div>}
      {loading ? (
        <div className="panel">报告加载中...</div>
      ) : !hasHistory ? (
        <section className="panel empty-state">
          <p>你还没有生成报告。</p>
          <Link className="button" to="/assessment">开始填写问卷</Link>
        </section>
      ) : (
        <>
          <section className="report-summary-grid">
            <div className="panel stat"><strong>{reports.length}</strong><span>已生成报告</span></div>
            <div className="panel stat"><strong>{activeCount}</strong><span>正在生成</span></div>
            <div className="panel stat"><strong>{failedCount}</strong><span>失败任务</span></div>
          </section>

          <section className="report-history">
            {jobs.map((job) => (
              <article className={`panel report-history-card report-job-card ${job.status}`} key={job.jobId}>
                <div>
                  <div className="report-history-head">
                    <h2>{jobStatusText(job)}</h2>
                    <span className={`job-status-pill ${job.status}`}>{job.progress}%</span>
                  </div>
                  <p className="hint">{jobTime(job)} · {job.message}</p>
                  {job.error && <p className="job-error">{job.error}</p>}
                  {isActiveJob(job) && (
                    <div className="job-progress-track">
                      <span style={{ width: `${job.progress}%` }} />
                    </div>
                  )}
                </div>
                <div className="report-history-actions">
                  {isActiveJob(job) && (
                    <button className="button secondary" disabled={cancellingJobId === job.jobId} onClick={() => cancelJob(job.jobId)}>
                      {cancellingJobId === job.jobId ? "取消中..." : "取消生成"}
                    </button>
                  )}
                  {job.status === "failed" && <Link className="button secondary" to="/assessment">重新填写</Link>}
                </div>
              </article>
            ))}
            {reports.map((report) => (
              <article className="panel report-history-card report-ready-card" key={report.id}>
                <div>
                  <div className="report-history-head">
                    <h2>{report.title}</h2>
                    <span className={`job-status-pill ${report.qualityStatus === "failed" ? "failed" : "success"}`}>
                      {qualityText(report.qualityStatus)}
                    </span>
                  </div>
                  <div className="report-card-meta">
                    <span>{new Date(report.createdAt).toLocaleString("zh-CN")}</span>
                    <span>{report.wordCount} 字</span>
                    {report.editedAt && <span>已人工修改</span>}
                  </div>
                </div>
                <div className="report-history-actions">
                  <button className="button secondary" onClick={() => editFromReport(report)}>修改问卷重新生成</button>
                  <button
                    className="button danger"
                    disabled={deletingReportId === report.id}
                    onClick={() => removeReport(report)}
                    type="button"
                  >
                    {deletingReportId === report.id ? "删除中..." : "删除"}
                  </button>
                  <Link className="button" to={`/reports/${report.id}`}>查看报告</Link>
                </div>
              </article>
            ))}
          </section>
        </>
      )}
    </main>
  );
}
