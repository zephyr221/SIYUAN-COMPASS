import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { changePassword } from "../api/auth";
import { useAuth } from "../auth/AuthContext";

export function HomePage() {
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submitPasswordChange(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (!currentPassword) {
      setError("请输入当前密码。");
      return;
    }
    if (newPassword.length < 8) {
      setError("新密码至少需要 8 位。");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("两次输入的新密码不一致。");
      return;
    }

    setSubmitting(true);
    try {
      const result = await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setSuccess(result.message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "密码修改失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="shell hero">
      <section>
        <h1>交小航——你的AI生涯伙伴</h1>
        <p className="lead">
          用8-12分钟完成首次填写，生成一份个性化《我的生涯蓝图》。系统会帮你梳理未来愿景、当前优势、路径风险和接下来6个月的行动建议。
        </p>
        <div className="actions" style={{ justifyContent: "flex-start" }}>
          <Link className="button" to="/assessment">开始填写</Link>
        </div>
      </section>
      {user?.authSource === "local" ? (
        <aside className="panel password-panel">
          <h2>修改密码</h2>
          <p className="hint">当前账号：{user.username}</p>
          <form onSubmit={submitPasswordChange}>
            <div className="field">
              <label htmlFor="current-password">当前密码</label>
              <input id="current-password" className="input" autoComplete="current-password" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="new-password">新密码</label>
              <input id="new-password" className="input" autoComplete="new-password" placeholder="至少 8 位" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="confirm-password">确认新密码</label>
              <input id="confirm-password" className="input" autoComplete="new-password" type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
            </div>
            {error && <div className="error">{error}</div>}
            {success && <div className="success">{success}</div>}
            <button className="button password-submit" disabled={submitting} type="submit">
              {submitting ? "修改中..." : "修改密码"}
            </button>
          </form>
        </aside>
      ) : !user ? (
        <aside className="panel">
          <h2>第一阶段闭环</h2>
          <p className="hint">首次填写、画像提取、状态判断、报告生成和反馈评分已经串成一条最小可用流程。</p>
          <div className="stat-grid">
            <div className="stat"><strong>24</strong><span>核心问题</span></div>
            <div className="stat"><strong>6</strong><span>生涯状态</span></div>
            <div className="stat"><strong>7+1</strong><span>报告结构</span></div>
            <div className="stat"><strong>4</strong><span>反馈评分</span></div>
          </div>
        </aside>
      ) : null}
    </main>
  );
}
