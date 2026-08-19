import { apiRequest } from "./client";
import type { AssessmentResponse } from "../types/assessment";
import type { AdminMetrics, AdminRecord, CareerBlueprintReport } from "../types/report";

export type AdminAuditLog = {
  id: string;
  adminId: string;
  adminDisplayName: string;
  action: string;
  targetType: string;
  targetId: string;
  createdAt: string;
  details: Record<string, unknown>;
};

export function fetchAdminMetrics() {
  return apiRequest<AdminMetrics>("/admin/metrics");
}

export function fetchAdminRecords() {
  return apiRequest<{ records: AdminRecord[] }>("/admin/records");
}

export function fetchAdminAuditLogs(limit = 20, offset = 0) {
  return apiRequest<{ total: number; items: AdminAuditLog[] }>(
    `/admin/audit-logs?limit=${limit}&offset=${offset}`
  );
}

export function fetchAdminAssessment(responseId: string) {
  return apiRequest<AssessmentResponse>(`/admin/assessments/${responseId}`);
}

export function updateAdminReport(reportId: string, title: string, content: string) {
  return apiRequest<CareerBlueprintReport>(`/admin/reports/${reportId}`, {
    method: "PUT",
    body: JSON.stringify({ title, content })
  });
}
