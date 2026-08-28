import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchAssessmentMaintenance } from "./maintenance";

describe("assessment maintenance API", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      active: true,
      message: "系统正在维护中"
    }), {
      headers: { "Content-Type": "application/json" },
      status: 200
    })));
  });

  it("读取公开维护状态", async () => {
    const status = await fetchAssessmentMaintenance();

    expect(status).toEqual({ active: true, message: "系统正在维护中" });
    expect((fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain("/assessment-maintenance");
  });
});
