import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function ProtectedRoute({
  children,
  role
}: {
  children: ReactNode;
  role?: "student" | "admin";
}) {
  const { loading, user } = useAuth();
  const location = useLocation();

  if (loading) {
    return <main className="shell page"><div className="panel">正在确认登录状态...</div></main>;
  }
  if (!user) {
    return <Navigate replace state={{ from: location.pathname }} to="/login" />;
  }
  if (role === "admin" && user.role !== "admin") {
    return <Navigate replace to="/assessment" />;
  }
  return children;
}
