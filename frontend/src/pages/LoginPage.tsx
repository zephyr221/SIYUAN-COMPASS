import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { jAccountLoginUrl, login } from "../api/auth";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { completeLogin } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const enableLocalAuth = import.meta.env.VITE_ENABLE_LOCAL_AUTH !== "false";
  const requested = (location.state as { from?: string } | null)?.from;

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!username.trim() || !password) {
      setError("请输入用户名和密码。");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const result = await login(username, password);
      completeLogin(result);
      navigate(requested || (result.user.role === "admin" ? "/admin" : "/assessment"), { replace: true });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "登录失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="shell auth-page">
      <form className="panel auth-card" onSubmit={submit}>
        <div className="auth-heading">
          <span className="auth-product-name">大学生生涯规划智能小助手</span>
          <h1>欢迎回来</h1>
          <p className="hint">使用学校统一身份认证，继续填写问卷或查看你的生涯蓝图。</p>
        </div>
        <a className="button auth-submit" href={jAccountLoginUrl(requested || "/assessment")}>使用 jAccount 登录</a>
        {enableLocalAuth && (
          <>
            <div className="auth-divider"><span>本地开发账号</span></div>
            <div className="field">
              <label>用户名</label>
              <input className="input" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} />
            </div>
            <div className="field">
              <label>密码</label>
              <input className="input" autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
            </div>
            {error && <div className="error">{error}</div>}
            <button className="button secondary auth-submit" disabled={submitting} type="submit">
              {submitting ? "登录中..." : "本地账号登录"}
            </button>
            <p className="auth-switch">仅限本地开发：<Link to="/register">注册测试账号</Link></p>
          </>
        )}
      </form>
    </main>
  );
}
