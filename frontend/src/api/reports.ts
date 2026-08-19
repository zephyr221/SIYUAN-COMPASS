import { apiRequest } from "./client";
import type { GenerationJobStatus } from "./assessments";
import type { CareerBlueprintReport } from "../types/report";

export function fetchReport(reportId: string) {
  return apiRequest<CareerBlueprintReport>(`/reports/${reportId}`);
}

export function fetchMyReports() {
  return apiRequest<{ reports: CareerBlueprintReport[]; jobs: GenerationJobStatus[] }>("/reports/mine");
}

export function deleteReport(reportId: string) {
  return apiRequest<{ message: string }>(`/reports/${reportId}`, { method: "DELETE" });
}

export function submitReportFeedback(
  reportId: string,
  body: {
    understandingScore: number;
    insightScore: number;
    actionScore: number;
    recommendScore: number;
    comment?: string;
  }
) {
  return apiRequest<{ feedbackId: string; createdAt: string }>(`/reports/${reportId}/feedback`, {
    method: "POST",
    body: JSON.stringify(body)
  });
}
