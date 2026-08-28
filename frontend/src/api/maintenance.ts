import { apiRequest } from "./client";

export type AssessmentMaintenanceStatus = {
  active: boolean;
  message: string;
};

export function fetchAssessmentMaintenance(signal?: AbortSignal) {
  return apiRequest<AssessmentMaintenanceStatus>("/assessment-maintenance", { signal });
}
