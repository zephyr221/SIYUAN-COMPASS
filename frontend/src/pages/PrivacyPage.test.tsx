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
    window.localStorage.setItem("siyuan_auth_user", JSON.stringify({
      displayName: "测试学生",
      id: "user-a",
      role: "student",
      username: "student-a"
    }));
    saveAssessmentDraft("user-a", { collegeMajor: "计算机" });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ message: "数据已清除" }), {
      headers: { "Content-Type": "application/json" },
      status: 200
    }));
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
