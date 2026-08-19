import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  ASSESSMENT_STORAGE_TTL_MS,
  clearAssessmentLocalData,
  clearExpiredAssessmentStorage,
  readAssessmentDraft,
  saveAssessmentDraft,
  saveAssessmentPrefill,
  takeAssessmentPrefill
} from "./assessmentStorage";

describe("assessmentStorage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.useRealTimers();
  });

  it("按用户隔离问卷草稿", () => {
    saveAssessmentDraft("user-a", { contactInfo: "a@example.com" });

    expect(readAssessmentDraft("user-b")).toBeNull();
    expect(readAssessmentDraft("user-a")).toEqual({ contactInfo: "a@example.com" });
  });

  it("本地草稿不保存已停用的问卷字段", () => {
    saveAssessmentDraft("user-a", {
      collegeMajor: "计算机",
      educationCertainty: 5,
      englishCertificates: "CET-6"
    });

    expect(readAssessmentDraft("user-a")).toEqual({ collegeMajor: "计算机" });
  });

  it("报告预填也不保存已停用的问卷字段", () => {
    saveAssessmentPrefill("user-a", { collegeMajor: "计算机", executionCase: "旧字段" });

    expect(takeAssessmentPrefill("user-a")).toEqual({ collegeMajor: "计算机" });
  });

  it("7 天后删除过期草稿", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-30T00:00:00Z"));
    saveAssessmentDraft("user-a", { studentName: "A" });
    vi.setSystemTime(Date.now() + ASSESSMENT_STORAGE_TTL_MS + 1);

    expect(readAssessmentDraft("user-a")).toBeNull();
    expect(window.localStorage.length).toBe(0);
  });

  it("应用启动清理所有账号的过期草稿但保留未过期草稿", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-01T00:00:00Z"));
    saveAssessmentDraft("user-a", { collegeMajor: "已过期" });
    vi.setSystemTime(Date.now() + ASSESSMENT_STORAGE_TTL_MS + 1);
    saveAssessmentDraft("user-b", { collegeMajor: "仍有效" });

    clearExpiredAssessmentStorage();

    expect(readAssessmentDraft("user-a")).toBeNull();
    expect(readAssessmentDraft("user-b")).toEqual({ collegeMajor: "仍有效" });
  });

  it("预填数据只能由所属用户读取一次", () => {
    saveAssessmentPrefill("user-a", { collegeMajor: "计算机" });

    expect(takeAssessmentPrefill("user-b")).toBeNull();
    expect(takeAssessmentPrefill("user-a")).toEqual({ collegeMajor: "计算机" });
    expect(takeAssessmentPrefill("user-a")).toBeNull();
  });

  it("退出只清理当前用户的草稿和预填", () => {
    saveAssessmentDraft("user-a", { studentName: "A" });
    saveAssessmentPrefill("user-a", { studentName: "A" });
    saveAssessmentDraft("user-b", { studentName: "B" });

    clearAssessmentLocalData("user-a");

    expect(readAssessmentDraft("user-a")).toBeNull();
    expect(takeAssessmentPrefill("user-a")).toBeNull();
    expect(readAssessmentDraft("user-b")).toEqual({ studentName: "B" });
  });
});
