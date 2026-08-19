const DRAFT_PREFIX = "siyuan_assessment_draft_v3";
const PREFILL_PREFIX = "siyuan_assessment_prefill_v2";
const LEGACY_KEYS = ["siyuan_assessment_draft_v2", "siyuan_assessment_prefill_v1"];
const SCOPED_PREFIXES = [`${DRAFT_PREFIX}:`, `${PREFILL_PREFIX}:`];
const NON_PERSISTED_DRAFT_FIELDS = [
  "educationCertainty",
  "englishCertificates",
  "academicExperiences",
  "executionCase",
  "negativeFeedbackReaction"
] as const;

export const ASSESSMENT_STORAGE_TTL_MS = 7 * 24 * 60 * 60 * 1000;

type StoredValue<T> = {
  expiresAt: number;
  userId: string;
  value: T;
  version: 1;
};

function scopedKey(prefix: string, userId: string) {
  return `${prefix}:${encodeURIComponent(userId)}`;
}

function writeScopedValue<T>(prefix: string, userId: string, value: T, now = Date.now()) {
  const record: StoredValue<T> = {
    expiresAt: now + ASSESSMENT_STORAGE_TTL_MS,
    userId,
    value,
    version: 1
  };
  window.localStorage.setItem(scopedKey(prefix, userId), JSON.stringify(record));
}

function readScopedValue<T>(prefix: string, userId: string, now = Date.now()): T | null {
  const key = scopedKey(prefix, userId);
  const raw = window.localStorage.getItem(key);
  if (!raw) return null;

  try {
    const record = JSON.parse(raw) as Partial<StoredValue<T>>;
    if (
      record.version !== 1
      || record.userId !== userId
      || typeof record.expiresAt !== "number"
      || record.expiresAt <= now
      || !("value" in record)
    ) {
      window.localStorage.removeItem(key);
      return null;
    }
    return record.value as T;
  } catch {
    window.localStorage.removeItem(key);
    return null;
  }
}

export function saveAssessmentDraft<T>(userId: string, value: T) {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    const safeValue = { ...(value as Record<string, unknown>) };
    NON_PERSISTED_DRAFT_FIELDS.forEach((field) => delete safeValue[field]);
    writeScopedValue(DRAFT_PREFIX, userId, safeValue as T);
    return;
  }
  writeScopedValue(DRAFT_PREFIX, userId, value);
}

export function readAssessmentDraft<T>(userId: string) {
  return readScopedValue<T>(DRAFT_PREFIX, userId);
}

export function removeAssessmentDraft(userId: string) {
  window.localStorage.removeItem(scopedKey(DRAFT_PREFIX, userId));
}

export function saveAssessmentPrefill<T>(userId: string, value: T) {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    const safeValue = { ...(value as Record<string, unknown>) };
    NON_PERSISTED_DRAFT_FIELDS.forEach((field) => delete safeValue[field]);
    writeScopedValue(PREFILL_PREFIX, userId, safeValue as T);
    return;
  }
  writeScopedValue(PREFILL_PREFIX, userId, value);
}

export function takeAssessmentPrefill<T>(userId: string) {
  const value = readScopedValue<T>(PREFILL_PREFIX, userId);
  window.localStorage.removeItem(scopedKey(PREFILL_PREFIX, userId));
  return value;
}

export function clearAssessmentLocalData(userId: string) {
  removeAssessmentDraft(userId);
  window.localStorage.removeItem(scopedKey(PREFILL_PREFIX, userId));
  clearLegacyAssessmentStorage();
}

export function clearLegacyAssessmentStorage() {
  LEGACY_KEYS.forEach((key) => window.localStorage.removeItem(key));
}

export function clearExpiredAssessmentStorage(now = Date.now()) {
  for (let index = window.localStorage.length - 1; index >= 0; index -= 1) {
    const key = window.localStorage.key(index);
    if (!key || !SCOPED_PREFIXES.some((prefix) => key.startsWith(prefix))) continue;

    const raw = window.localStorage.getItem(key);
    try {
      const record = raw ? JSON.parse(raw) as Partial<StoredValue<unknown>> : null;
      if (
        !record
        || record.version !== 1
        || typeof record.userId !== "string"
        || !SCOPED_PREFIXES.some((prefix) => key === `${prefix}${encodeURIComponent(record.userId || "")}`)
        || typeof record.expiresAt !== "number"
        || record.expiresAt <= now
        || !("value" in record)
      ) {
        window.localStorage.removeItem(key);
      }
    } catch {
      window.localStorage.removeItem(key);
    }
  }
}
