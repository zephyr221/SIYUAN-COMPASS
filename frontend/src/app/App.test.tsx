import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { App } from "./App";

function renderApp(path: string) {
  return render(
    <MemoryRouter future={{ v7_relativeSplatPath: true, v7_startTransition: true }} initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("App", () => {
  it("为未知地址显示 404 页面而不是空白页", () => {
    renderApp("/does-not-exist");

    expect(screen.getByRole("heading", { name: "页面不存在" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回首页" })).toHaveAttribute("href", "/");
  });

  it("所有页面提供隐私政策入口", () => {
    renderApp("/");

    expect(screen.getByRole("link", { name: "隐私政策与数据管理" })).toHaveAttribute("href", "/privacy");
  });

  it("为退出按钮提供手机端隐藏标识", () => {
    window.localStorage.setItem("siyuan_auth_token", "token");
    window.localStorage.setItem("siyuan_auth_user", JSON.stringify({
      displayName: "测试学生",
      id: "user-a",
      role: "student",
      username: "student-a"
    }));
    renderApp("/");

    expect(screen.getByRole("button", { name: "退出" })).toHaveClass("nav-logout");
  });
});
