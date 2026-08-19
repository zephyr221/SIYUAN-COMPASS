import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { readAssessmentDraft, saveAssessmentDraft } from "../storage/assessmentStorage";
import { PrivacyPage } from "./PrivacyPage";

describe("PrivacyPage", () => {
  it("二次确认后清除服务端业务数据和本地草稿", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("siyuan_auth_token", "token");
    const currentUser = {
      // authSource 由 sjtu-production 分支引入。
      authSource: "local",
      displayName: "测试学生",
      id: "user-a",
      role: "student",
      username: "student-a"
    };
    window.localStorage.setItem("siyuan_auth_user", JSON.stringify(currentUser));
    saveAssessmentDraft("user-a", { collegeMajor: "计算机" });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    // 本分支的 AuthProvider 在挂载时会探测 /auth/me（门户 jAccount 会话可能已经登录），
    // 所以 mock 必须按 URL 分流：一律返回 {message} 会让 role 变成 undefined，
    // 清除按钮根本不渲染，本用例就会以「找不到 status」的形式假失败。
    const json = (body: unknown) => new Response(JSON.stringify(body), {
      headers: { "Content-Type": "application/json" },
      status: 200
    });
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(String(input).endsWith("/auth/me") ? json(currentUser) : json({ message: "数据已清除" }))
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
        <AuthProvider>
          <PrivacyPage />
        </AuthProvider>
      </MemoryRouter>
    );
    await user.click(screen.getByRole("button", { name: "清除我的全部业务数据" }));

    expect(await screen.findByRole("status")).toHaveTextContent("数据已清除");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/privacy\/my-data$/),
      expect.objectContaining({ method: "DELETE" })
    );
    expect(readAssessmentDraft("user-a")).toBeNull();
  });
});
