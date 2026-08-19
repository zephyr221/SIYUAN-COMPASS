import { beforeEach, describe, expect, it, vi } from "vitest";
import { AUTH_UNAUTHORIZED_EVENT } from "../auth/AuthContext";
import { apiRequest } from "./client";

describe("apiRequest", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("在非 JSON 错误页时返回可理解的 HTTP 错误", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>Bad Gateway</html>", { status: 502 })));

    await expect(apiRequest("/reports/mine")).rejects.toThrow("请求失败（HTTP 502）");
  });

  it("保留网关返回的简短纯文本错误", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Service unavailable", { status: 503 })));

    await expect(apiRequest("/reports/mine")).rejects.toThrow("Service unavailable");
  });

  it("已登录请求收到 401 时清理失效认证信息", async () => {
    window.localStorage.setItem("siyuan_auth_token", "expired-token");
    window.localStorage.setItem("siyuan_auth_user", JSON.stringify({ id: "user-a" }));
    const listener = vi.fn();
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, listener);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Unauthorized" }), {
      headers: { "Content-Type": "application/json" },
      status: 401
    })));

    await expect(apiRequest("/auth/me")).rejects.toThrow("登录状态已失效，请重新登录。");
    expect(window.localStorage.getItem("siyuan_auth_token")).toBeNull();
    expect(window.localStorage.getItem("siyuan_auth_user")).toBeNull();
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, listener);
  });

  it("不将主动取消误报为网络故障", async () => {
    const abortError = new DOMException("已取消", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abortError));

    await expect(apiRequest("/assessment-jobs/job-a")).rejects.toBe(abortError);
  });

  it("上传 FormData 时不手动覆盖浏览器生成的 multipart 边界", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ text: "你好" }), {
      headers: { "Content-Type": "application/json" },
      status: 200
    }));
    vi.stubGlobal("fetch", fetchMock);
    const body = new FormData();
    body.append("audio", new Blob(["audio"], { type: "audio/webm" }), "recording.webm");

    await apiRequest("/speech/transcribe", { method: "POST", body });

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(request.headers).get("Content-Type")).toBeNull();
    expect(request.body).toBe(body);
  });
});
