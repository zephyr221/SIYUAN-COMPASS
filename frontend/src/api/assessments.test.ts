import { beforeEach, describe, expect, it, vi } from "vitest";
import { deleteAssessmentDraft, fetchAssessmentDraft, saveAssessmentDraft } from "./assessments";

describe("assessment draft API", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ draft: null }), {
      headers: { "Content-Type": "application/json" },
      status: 200
    })));
  });

  it("按约定调用云端草稿读取接口", async () => {
    await fetchAssessmentDraft();
    const request = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    expect((fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain("/assessment-draft");
    expect(request.method).toBeUndefined();
  });

  it("保存草稿携带当前步骤和版本", async () => {
    const response = {
      id: "draft-1",
      userId: "user-1",
      answers: { collegeMajor: "计算机" },
      currentStep: 2,
      version: 3,
      createdAt: "2026-08-01T00:00:00Z",
      updatedAt: "2026-08-01T00:01:00Z",
      expiresAt: "2026-08-31T00:01:00Z"
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(response), {
      headers: { "Content-Type": "application/json" },
      status: 200
    })));
    await saveAssessmentDraft({ answers: { collegeMajor: "计算机" } as never, currentStep: 2, version: 2 });
    const request = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    expect(request.method).toBe("PUT");
    expect(JSON.parse(String(request.body))).toEqual({
      answers: { collegeMajor: "计算机" },
      currentStep: 2,
      version: 2
    });
  });

  it("支持删除云端草稿", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ deleted: true }), {
      headers: { "Content-Type": "application/json" },
      status: 200
    })));
    await deleteAssessmentDraft();
    const request = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    expect(request.method).toBe("DELETE");
  });
});
