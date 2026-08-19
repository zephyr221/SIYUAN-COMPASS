import { apiRequest } from "./client";
import type { AssessmentResponseInput } from "../types/assessment";

export type AssessmentSubmitResult = {
  userId: string;
  responseId: string;
  profileId: string;
  reportId: string;
  generationStatus: string;
};

export type GenerationJobStatus = {
  jobId: string;
  status: "queued" | "running" | "success" | "failed" | "cancelled";
  stage: string;
  progress: number;
  message: string;
  userId?: string;
  responseId?: string;
  profileId?: string;
  reportId?: string;
  generationStatus?: string;
  error?: string;
  createdAt?: string;
  updatedAt?: string;
};

export type AssessmentDraft = {
  id: string;
  userId: string;
  answers: Partial<AssessmentResponseInput> & Record<string, unknown>;
  currentStep: number;
  version: number;
  createdAt: string;
  updatedAt: string;
  expiresAt: string;
};

export function submitAssessment(input: AssessmentResponseInput & { userId?: string }) {
  return apiRequest<AssessmentSubmitResult>("/assessments", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function createAssessmentJob(input: AssessmentResponseInput & { userId?: string }, signal?: AbortSignal) {
  return apiRequest<{ jobId: string; status: "queued" }>("/assessment-jobs", {
    method: "POST",
    body: JSON.stringify(input),
    signal
  });
}

export function fetchAssessmentJob(jobId: string, signal?: AbortSignal) {
  return apiRequest<GenerationJobStatus>(`/assessment-jobs/${jobId}`, { signal });
}

export function cancelAssessmentJob(jobId: string) {
  return apiRequest<GenerationJobStatus>(`/assessment-jobs/${jobId}/cancel`, {
    method: "POST"
  });
}

export function fetchAssessmentDraft(signal?: AbortSignal) {
  return apiRequest<{ draft: AssessmentDraft | null }>("/assessment-draft", { signal });
}

export function saveAssessmentDraft(
  input: { answers: AssessmentResponseInput; currentStep: number; version: number },
  signal?: AbortSignal
) {
  return apiRequest<AssessmentDraft>("/assessment-draft", {
    method: "PUT",
    body: JSON.stringify(input),
    signal
  });
}

export function deleteAssessmentDraft() {
  return apiRequest<{ deleted: boolean }>("/assessment-draft", { method: "DELETE" });
}
