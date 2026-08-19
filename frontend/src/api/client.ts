import { AUTH_UNAUTHORIZED_EVENT, clearStoredAuth, getAuthToken } from "../auth/AuthContext";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export function apiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}

export async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const requestHeaders = new Headers(options?.headers);
  if (!(options?.body instanceof FormData) && !requestHeaders.has("Content-Type")) {
    requestHeaders.set("Content-Type", "application/json");
  }
  if (token) requestHeaders.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    // credentials: "include" 让门户签名 session cookie 随请求发出，jAccount 登录依赖它。
    response = await fetch(apiUrl(path), {
      credentials: "include",
      ...options,
      headers: requestHeaders
    });
  } catch (caught) {
    if (caught instanceof DOMException && caught.name === "AbortError") throw caught;
    throw new Error("网络连接失败，请检查网络后重试。");
  }

  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    if (response.status === 401 && token) {
      clearStoredAuth();
      window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
    }

    const objectData = isRecord(data) ? data : null;
    const detail = objectData?.detail;
    const detailObject = isRecord(detail) ? detail : null;
    const stagedError = typeof detailObject?.stage === "string" && typeof detailObject.error === "string"
      ? `${detailObject.stage}：${detailObject.error}`
      : undefined;
    const detailErrors = Array.isArray(detailObject?.errors)
      ? detailObject.errors.filter((item): item is string => typeof item === "string").join("；")
      : undefined;
    const plainText = typeof data === "string" && !/<\/?(?:html|body)[\s>]/i.test(data)
      ? data.trim().slice(0, 240)
      : undefined;
    const message = response.status === 401 && token
      ? "登录状态已失效，请重新登录。"
      : stagedError
        || detailErrors
        || (typeof detailObject?.error === "string" ? detailObject.error : undefined)
        || (typeof detail === "string" ? detail : undefined)
        || (typeof objectData?.error === "string" ? objectData.error : undefined)
        || plainText
        || `请求失败（HTTP ${response.status}）`;
    const error = new Error(message) as Error & { fieldErrors?: Record<string, string>; status?: number };
    error.status = response.status;
    if (isStringRecord(detailObject?.fieldErrors)) {
      error.fieldErrors = detailObject.fieldErrors;
    }
    throw error;
  }

  return data as T;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringRecord(value: unknown): value is Record<string, string> {
  return isRecord(value) && Object.values(value).every((item) => typeof item === "string");
}
