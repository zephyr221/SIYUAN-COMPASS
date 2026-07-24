import { Link, NavLink, Route, Routes } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ProtectedRoute } from "../auth/ProtectedRoute";
import { AdminAssessmentPage } from "../pages/AdminAssessmentPage";
import { AdminPage } from "../pages/AdminPage";
import { AdminReportEditPage } from "../pages/AdminReportEditPage";
import { AssessmentPage } from "../pages/AssessmentPage";
import { FeedbackPage } from "../pages/FeedbackPage";
import { HomePage } from "../pages/HomePage";
import { LoginPage } from "../pages/LoginPage";
import { MyReportsPage } from "../pages/MyReportsPage";
import { RegisterPage } from "../pages/RegisterPage";
import { ReportPage } from "../pages/ReportPage";

export function App() {
  const { user, logout } = useAuth();
  const enableLocalAuth = import.meta.env.VITE_ENABLE_LOCAL_AUTH !== "false";

  return (
    <>
      <header className="topbar">
        <div className="shell topbar-inner">
          <Link className="brand" to="/">大学生生涯规划智能小助手</Link>
          <nav className="nav">
            {user?.role === "student" && <NavLink to="/assessment">开始填写</NavLink>}
            {user?.role === "student" && <NavLink to="/my-reports">我的报告</NavLink>}
            {user?.role === "admin" && <NavLink to="/admin">管理员后台</NavLink>}
            {user ? (
              <>
                <span className="nav-user">{user.displayName}</span>
                <button className="nav-button" onClick={logout}>退出</button>
              </>
            ) : (
              <NavLink to="/login">登录</NavLink>
            )}
          </nav>
        </div>
      </header>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        {enableLocalAuth && <Route path="/register" element={<RegisterPage />} />}
        <Route path="/assessment" element={<ProtectedRoute role="student"><AssessmentPage /></ProtectedRoute>} />
        <Route path="/my-reports" element={<ProtectedRoute role="student"><MyReportsPage /></ProtectedRoute>} />
        <Route path="/reports/:reportId" element={<ProtectedRoute><ReportPage /></ProtectedRoute>} />
        <Route path="/reports/:reportId/feedback" element={<ProtectedRoute role="student"><FeedbackPage /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute role="admin"><AdminPage /></ProtectedRoute>} />
        <Route path="/admin/assessments/:responseId" element={<ProtectedRoute role="admin"><AdminAssessmentPage /></ProtectedRoute>} />
        <Route path="/admin/reports/:reportId/edit" element={<ProtectedRoute role="admin"><AdminReportEditPage /></ProtectedRoute>} />
      </Routes>
    </>
  );
}
