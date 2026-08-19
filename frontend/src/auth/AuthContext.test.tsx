import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { readAssessmentDraft, saveAssessmentDraft } from "../storage/assessmentStorage";
import { AUTH_UNAUTHORIZED_EVENT, AuthProvider, useAuth } from "./AuthContext";

function AccountSwitcher() {
  const { completeLogin } = useAuth();
  return (
    <button
      onClick={() => completeLogin({
        token: "token-b",
        user: {
          displayName: "学生 B",
          id: "user-b",
          role: "student",
          username: "student-b"
        }
      })}
      type="button"
    >
      切换账号
    </button>
  );
}

describe("AuthProvider", () => {
  it("切换账号时清理上一账号草稿且不读取新账号草稿", () => {
    window.localStorage.setItem("siyuan_auth_token", "token-a");
    window.localStorage.setItem("siyuan_auth_user", JSON.stringify({
      displayName: "学生 A",
      id: "user-a",
      role: "student",
      username: "student-a"
    }));
    saveAssessmentDraft("user-a", { collegeMajor: "账号 A 的草稿" });
    saveAssessmentDraft("user-b", { collegeMajor: "账号 B 的草稿" });
    render(<AuthProvider><AccountSwitcher /></AuthProvider>);

    fireEvent.click(screen.getByRole("button", { name: "切换账号" }));

    expect(readAssessmentDraft("user-a")).toBeNull();
    expect(readAssessmentDraft("user-b")).toEqual({ collegeMajor: "账号 B 的草稿" });
    expect(JSON.parse(window.localStorage.getItem("siyuan_auth_user") || "{}").id).toBe("user-b");
  });

  it("登录失效时按强制退出处理并清理当前账号草稿", () => {
    window.localStorage.setItem("siyuan_auth_token", "token-a");
    window.localStorage.setItem("siyuan_auth_user", JSON.stringify({
      displayName: "学生 A",
      id: "user-a",
      role: "student",
      username: "student-a"
    }));
    saveAssessmentDraft("user-a", { collegeMajor: "账号 A 的草稿" });
    render(<AuthProvider><div>应用内容</div></AuthProvider>);

    act(() => window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT)));

    expect(readAssessmentDraft("user-a")).toBeNull();
  });
});
