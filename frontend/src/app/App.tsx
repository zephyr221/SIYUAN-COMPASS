import { Link, NavLink, Route, Routes } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ProtectedRoute } from "../auth/ProtectedRoute";
import { AppFooter } from "../components/AppFooter";
import { AdminAssessmentPage } from "../pages/AdminAssessmentPage";
import { AdminPage } from "../pages/AdminPage";
import { AdminReportEditPage } from "../pages/AdminReportEditPage";
import { AssessmentClosedPage } from "../pages/AssessmentClosedPage";
import { FeedbackPage } from "../pages/FeedbackPage";
import { HomePage } from "../pages/HomePage";
import { LoginPage } from "../pages/LoginPage";
import { MyReportsPage } from "../pages/MyReportsPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { PrivacyPage } from "../pages/PrivacyPage";
import { RegisterPage } from "../pages/RegisterPage";
import { ReportPage } from "../pages/ReportPage";

export function App() {
  const { user, logout } = useAuth();
  const enableLocalAuth = import.meta.env.VITE_ENABLE_LOCAL_AUTH !== "false";

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="shell topbar-inner">
          <Link className="brand" to="/">交小航——你的AI生涯伙伴</Link>
          <nav className="nav">
            {user && <NavLink to="/assessment">填写已关闭</NavLink>}
            {user && <NavLink to="/my-reports">我的报告</NavLink>}
            {user?.role === "admin" && <NavLink to="/admin">管理员后台</NavLink>}
            {user ? (
              <>
                <span className="nav-user">{user.displayName}</span>
                <button className="nav-button nav-logout" onClick={logout}>退出</button>
              </>
            ) : (
              <NavLink to="/login">登录</NavLink>
            )}
          </nav>
        </div>
      </header>
      <div className="app-content">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          {/* 生产环境走 jAccount，本地注册入口整条路由都不挂。 */}
          {enableLocalAuth && <Route path="/register" element={<RegisterPage />} />}
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/assessment" element={<ProtectedRoute role="student"><AssessmentClosedPage /></ProtectedRoute>} />
          <Route path="/my-reports" element={<ProtectedRoute role="student"><MyReportsPage /></ProtectedRoute>} />
          <Route path="/reports/:reportId" element={<ProtectedRoute><ReportPage /></ProtectedRoute>} />
          <Route path="/reports/:reportId/feedback" element={<ProtectedRoute role="student"><FeedbackPage /></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute role="admin"><AdminPage /></ProtectedRoute>} />
          <Route path="/admin/assessments/:responseId" element={<ProtectedRoute role="admin"><AdminAssessmentPage /></ProtectedRoute>} />
          <Route path="/admin/reports/:reportId/edit" element={<ProtectedRoute role="admin"><AdminReportEditPage /></ProtectedRoute>} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </div>
      <AppFooter />
    </div>
  );
}
