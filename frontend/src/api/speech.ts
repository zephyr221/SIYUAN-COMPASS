import { apiRequest } from "./client";

export type SpeechStatus = {
  provider: string;
  configured: boolean;
  model: string | null;
  maxFileMb: number;
  dailyLimit: number;
};

export function fetchSpeechStatus() {
  return apiRequest<SpeechStatus>("/speech/status");
}

export function transcribeAudio(blob: Blob, filename = "recording.webm", language = "zh-CN") {
  const body = new FormData();
  body.append("audio", blob, filename);
  body.append("language", language);
  return apiRequest<{ text: string }>("/speech/transcribe", {
    method: "POST",
    body
  });
}
