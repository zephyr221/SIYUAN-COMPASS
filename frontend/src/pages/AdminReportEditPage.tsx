import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { updateAdminReport } from "../api/admin";
import { fetchReport } from "../api/reports";

export function AdminReportEditPage() {
  const { reportId } = useParams();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!reportId) return;
    fetchReport(reportId)
      .then((report) => {
        setTitle(report.title);
        setContent(report.content);
      })
      .catch((caught) => setStatus(caught instanceof Error ? caught.message : "报告加载失败"))
      .finally(() => setLoading(false));
  }, [reportId]);

  async function save() {
    if (!reportId) return;
    setSaving(true);
    setStatus("");
    try {
      const report = await updateAdminReport(reportId, title, content);
      setContent(report.content);
      setStatus("报告已保存，学生再次打开时会看到修改后的版本。");
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <main className="shell page"><div className="panel">报告加载中...</div></main>;
  }

  return (
    <main className="shell page">
      <div className="page-title">
        <h1>编辑学生报告</h1>
        <p>保留 Markdown 标题和列表格式，保存后会立即覆盖当前报告正文。</p>
      </div>
      <section className="panel report-editor">
        <p className="privacy-notice">
          报告会向学生长期展示，请勿加入姓名、学号、联系方式或其他不必要的身份信息；明显的手机号、邮箱和长数字标识会被拒绝保存。
        </p>
        <div className="field">
          <label>报告标题</label>
          <input className="input" value={title} onChange={(event) => setTitle(event.target.value)} />
        </div>
        <div className="field">
          <label>报告正文</label>
          <textarea className="textarea report-editor-content" value={content} onChange={(event) => setContent(event.target.value)} />
        </div>
        {status && <div className={status.startsWith("报告已保存") ? "success" : "error"}>{status}</div>}
        <div className="actions">
          <Link className="button secondary" to="/admin">返回后台</Link>
          {reportId && <Link className="button secondary" to={`/reports/${reportId}`}>预览报告</Link>}
          <button className="button" disabled={saving || !title.trim() || !content.trim()} onClick={save}>
            {saving ? "保存中..." : "保存修改"}
          </button>
        </div>
      </section>
    </main>
  );
}
