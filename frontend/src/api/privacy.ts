import { apiRequest } from "./client";

export function deleteMyBusinessData() {
  return apiRequest<{ message: string }>("/privacy/my-data", { method: "DELETE" });
}
