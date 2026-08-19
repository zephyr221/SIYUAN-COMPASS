from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.core.config import get_settings
from app.core.data_privacy import redact_obvious_contact_details
from app.schemas.assessment import AssessmentResponse, AssessmentResponseInput
from app.schemas.generation_job import GenerationJobStatus
from app.schemas.profile import CareerProfile
from app.schemas.report import CareerBlueprintReport, ReportFeedback

ASSESSMENT_LIST_FIELDS = (
    "educationPathReasons",
    "topValuesRanked",
    "praisedTraits",
    "currentPreparations",
    "missingResources",
    "jobInfoChannels",
    "careerConfusions",
)

ASSESSMENT_DIRECT_IDENTIFIER_FIELDS = (
    "studentName",
    "school",
    "studentNumber",
    "contactInfo",
)

ASSESSMENT_NON_PERSISTED_FIELDS = (
    "educationCertainty",
    "englishCertificates",
    "academicExperiences",
    "executionCase",
    "negativeFeedbackReaction",
)

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE,
    display_name TEXT,
    password_hash TEXT,
    auth_source TEXT NOT NULL DEFAULT 'local',
    role TEXT NOT NULL DEFAULT 'student',
    generation_quota_day DATE,
    generation_quota_used INTEGER NOT NULL DEFAULT 0,
    speech_quota_day DATE,
    speech_quota_used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_source TEXT NOT NULL DEFAULT 'local';
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS generation_quota_day DATE;
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS generation_quota_used INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS speech_quota_day DATE;
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS speech_quota_used INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS assessment_responses (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    grade TEXT NOT NULL,
    college_major TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS assessment_scores (
    assessment_id TEXT PRIMARY KEY REFERENCES assessment_responses(id) ON DELETE CASCADE,
    ability_scores JSONB NOT NULL,
    interest_scores JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS assessment_choices (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES assessment_responses(id) ON DELETE CASCADE,
    question_code TEXT NOT NULL,
    option_value TEXT NOT NULL,
    sort_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS assessment_drafts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    answers JSONB NOT NULL,
    current_step INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS career_profiles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    response_id TEXT NOT NULL REFERENCES assessment_responses(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    response_id TEXT NOT NULL REFERENCES assessment_responses(id) ON DELETE CASCADE,
    profile_id TEXT NOT NULL REFERENCES career_profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    generation_status TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    edited_at TEXT,
    edited_by TEXT,
    data JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS report_versions (
    id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    word_count INTEGER NOT NULL,
    quality_status TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT,
    generation_job_id TEXT
);

ALTER TABLE report_versions
    ADD COLUMN IF NOT EXISTS generation_job_id TEXT;

CREATE TABLE IF NOT EXISTS generation_jobs (
    job_id TEXT PRIMARY KEY,
    user_id TEXT,
    status TEXT NOT NULL,
    stage TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    input_data JSONB,
    claim_token TEXT,
    lease_expires_at TIMESTAMPTZ,
    data JSONB NOT NULL
);

ALTER TABLE generation_jobs
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;
ALTER TABLE generation_jobs
    ADD COLUMN IF NOT EXISTS input_data JSONB;
ALTER TABLE generation_jobs
    ADD COLUMN IF NOT EXISTS claim_token TEXT;
ALTER TABLE generation_jobs
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;
UPDATE generation_jobs SET created_at = updated_at WHERE created_at IS NULL;
ALTER TABLE generation_jobs ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE generation_jobs ALTER COLUMN created_at SET NOT NULL;

CREATE TABLE IF NOT EXISTS report_feedback (
    id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    understanding_score INTEGER NOT NULL,
    insight_score INTEGER NOT NULL,
    action_score INTEGER NOT NULL,
    recommend_score INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    data JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id TEXT PRIMARY KEY,
    admin_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    details JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assessment_responses_user_id
    ON assessment_responses(user_id);
CREATE INDEX IF NOT EXISTS idx_assessment_choices_assessment_id
    ON assessment_choices(assessment_id);
CREATE INDEX IF NOT EXISTS idx_assessment_drafts_expires_at
    ON assessment_drafts(expires_at);
CREATE INDEX IF NOT EXISTS idx_career_profiles_response_id
    ON career_profiles(response_id);
CREATE INDEX IF NOT EXISTS idx_reports_user_id_created_at
    ON reports(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_reports_created_at
    ON reports(created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_report_versions_generation_job_id
    ON report_versions(generation_job_id)
    WHERE generation_job_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_report_feedback_report_id
    ON report_feedback(report_id);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_user_status_updated_at
    ON generation_jobs(user_id, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_user_created_at
    ON generation_jobs(user_id, created_at);
"""


class GenerationQuotaStorageError(RuntimeError):
    def __init__(self, *, limit: int, used: int) -> None:
        self.limit = limit
        self.used = used
        super().__init__(f"当日报告生成次数已达上限（{used}/{limit}）")


class SpeechQuotaStorageError(RuntimeError):
    def __init__(self, *, limit: int, used: int) -> None:
        self.limit = limit
        self.used = used
        super().__init__(f"当日语音转写次数已达上限（{used}/{limit}）")


class AssessmentDraftConflictError(RuntimeError):
    def __init__(self, current: dict[str, Any]) -> None:
        self.current = current
        super().__init__("草稿已在其他设备更新")


@contextmanager
def _connect():
    connection = psycopg.connect(get_settings().database_url, row_factory=dict_row)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def ensure_storage() -> None:
    with _connect() as connection:
        connection.execute(CREATE_TABLES_SQL)


def get_or_create_user(user_id: str | None = None) -> dict[str, Any]:
    from app.services.report_generator import now_iso

    existing = find_user(user_id) if user_id else None
    if existing:
        return existing

    now = now_iso()
    user = {
        "id": user_id or str(uuid4()),
        "username": None,
        "displayName": "匿名用户",
        "passwordHash": "",
        "role": "student",
        "createdAt": now,
        "updatedAt": now,
    }
    with _connect() as connection:
        _upsert_user(connection, user)
    return user


def _user_from_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "displayName": row["display_name"],
        "passwordHash": row["password_hash"],
        "authSource": row.get("auth_source") or "local",
        "role": row["role"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def find_user(user_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()
    return _user_from_row(row)


def find_user_by_username(username: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE username = %s",
            (username,),
        ).fetchone()
    return _user_from_row(row)


def update_user_password(user_id: str, password_hash: str) -> bool:
    with _connect() as connection:
        result = connection.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (password_hash, user_id),
        )
    return result.rowcount == 1


def _upsert_user(connection, user: dict[str, Any]) -> None:
    connection.execute(
        """
        INSERT INTO users (
            id, username, display_name, password_hash, auth_source, role, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            username = EXCLUDED.username,
            display_name = EXCLUDED.display_name,
            password_hash = EXCLUDED.password_hash,
            auth_source = EXCLUDED.auth_source,
            role = EXCLUDED.role,
            updated_at = EXCLUDED.updated_at
        """,
        (
            user["id"],
            user.get("username"),
            user.get("displayName"),
            user.get("passwordHash"),
            user.get("authSource", "local"),
            user.get("role", "student"),
            user["createdAt"],
            user["updatedAt"],
        ),
    )


def create_account(
    *,
    username: str,
    display_name: str,
    password_hash: str,
    role: Literal["student", "admin"],
) -> dict[str, Any]:
    from app.services.report_generator import now_iso

    now = now_iso()
    user = {
        "id": str(uuid4()),
        "username": username,
        "displayName": display_name,
        "passwordHash": password_hash,
        "authSource": "local",
        "role": role,
        "createdAt": now,
        "updatedAt": now,
    }
    with _connect() as connection:
        _upsert_user(connection, user)
    return user


def ensure_admin_account() -> None:
    from app.core.config import get_settings
    from app.services.auth import hash_password, normalize_username

    settings = get_settings()
    if not settings.local_auth_enabled:
        return
    username = normalize_username(settings.admin_username)
    if find_user_by_username(username):
        return
    create_account(
        username=username,
        display_name=settings.admin_display_name,
        password_hash=hash_password(settings.admin_password),
        role="admin",
    )


def upsert_jaccount_user(*, username: str, display_name: str) -> dict[str, Any]:
    from app.services.report_generator import now_iso

    now = now_iso()
    normalized = username.strip().lower()
    with _connect() as connection:
        row = connection.execute(
            """
            INSERT INTO users (
                id, username, display_name, password_hash, auth_source,
                role, created_at, updated_at
            )
            VALUES (%s, %s, %s, '', 'jaccount', %s, %s, %s)
            ON CONFLICT (username) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                auth_source = 'jaccount',
                role = users.role,
                updated_at = EXCLUDED.updated_at
            RETURNING *
            """,
            (
                str(uuid4()),
                normalized,
                display_name.strip() or normalized,
                "student",
                now,
                now,
            ),
        ).fetchone()
    user = _user_from_row(row)
    if not user:
        raise RuntimeError("jAccount 用户写入失败")
    return user


def set_jaccount_user_role(*, username: str, role: Literal["student", "admin"]) -> dict[str, Any]:
    from app.services.report_generator import now_iso

    now = now_iso()
    normalized = username.strip().lower()
    if not normalized:
        raise ValueError("jAccount username cannot be empty")

    with _connect() as connection:
        row = connection.execute(
            """
            INSERT INTO users (
                id, username, display_name, password_hash, auth_source,
                role, created_at, updated_at
            )
            VALUES (%s, %s, %s, '', 'jaccount', %s, %s, %s)
            ON CONFLICT (username) DO UPDATE SET
                role = EXCLUDED.role,
                updated_at = EXCLUDED.updated_at
            WHERE users.auth_source = 'jaccount'
            RETURNING *
            """,
            (str(uuid4()), normalized, normalized, role, now, now),
        ).fetchone()

    user = _user_from_row(row)
    if not user:
        raise RuntimeError("Cannot change a local account through jAccount role management")
    return user


def _response_storage_record(response: AssessmentResponse) -> dict[str, Any]:
    record = response.model_dump(mode="json")
    record.pop("abilityScores")
    record.pop("interestScores")
    for question_code in ASSESSMENT_LIST_FIELDS:
        record.pop(question_code)
    for field in ASSESSMENT_NON_PERSISTED_FIELDS:
        record.pop(field, None)
    return record


def _profile_storage_record(profile: CareerProfile) -> dict[str, Any]:
    record = profile.model_dump(mode="json")
    record.pop("rawModelOutput", None)
    return record


def _generation_input_storage_record(input_data: dict[str, Any]) -> dict[str, Any]:
    """Persist only fields allowed to survive beyond the request boundary.

    Older clients can still submit deprecated properties accepted for schema
    compatibility. Strip only those values that are never needed after the
    request boundary; the collected identity, gender and income fields remain
    in the recoverable input so the completed assessment snapshot is complete.
    """
    forbidden_values: set[str] = set()
    for field in ASSESSMENT_DIRECT_IDENTIFIER_FIELDS:
        value = input_data.get(field)
        if isinstance(value, str) and value.strip():
            forbidden_values.add(value.strip())

    def redact(value: Any) -> Any:
        if isinstance(value, str):
            for forbidden in sorted(forbidden_values, key=len, reverse=True):
                value = value.replace(forbidden, "[已脱敏]")
            return redact_obvious_contact_details(value)
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items()}
        return value

    # Keep the submitted values in their own fields. The redaction pass is
    # for accidental repeats inside free-text answers; applying it back to the
    # dedicated fields would make the completed assessment incomplete.
    preserved_fields = {
        field_name: input_data.get(field_name)
        for field_name in (
            *ASSESSMENT_DIRECT_IDENTIFIER_FIELDS,
            "gender",
            "fiveYearIncome",
            "tenYearIncome",
        )
        if field_name in input_data
    }
    record = redact(input_data)
    record.update(preserved_fields)
    for field in ASSESSMENT_NON_PERSISTED_FIELDS:
        record.pop(field, None)
    return record


def _draft_storage_record(answers: dict[str, Any]) -> dict[str, Any]:
    """Keep only questionnaire fields that are safe and useful to restore.

    Drafts are never sent to the model. They may contain partially completed
    values, so they intentionally do not go through the complete response
    validator. Unknown keys and request-only fields are discarded here to
    prevent a client from turning the draft table into an arbitrary JSON store.
    """
    allowed_fields = set(AssessmentResponseInput.model_fields) - {"userId"}
    record = {key: value for key, value in answers.items() if key in allowed_fields}
    for field in ASSESSMENT_NON_PERSISTED_FIELDS:
        record.pop(field, None)
    return record


def _assessment_draft_from_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "id": row["id"],
        "userId": row["user_id"],
        "answers": _draft_storage_record(dict(row["answers"] or {})),
        "currentStep": int(row["current_step"]),
        "version": int(row["version"]),
        "createdAt": _iso_timestamp(row["created_at"]),
        "updatedAt": _iso_timestamp(row["updated_at"]),
        "expiresAt": _iso_timestamp(row["expires_at"]),
    }


def get_assessment_draft(user_id: str) -> dict[str, Any] | None:
    """Return the current account's unexpired draft, if one exists."""
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, user_id, answers, current_step, version,
                   created_at, updated_at, expires_at
            FROM assessment_drafts
            WHERE user_id = %s
            """,
            (user_id,),
        ).fetchone()
        if row and row["expires_at"] <= datetime.now(timezone.utc):
            connection.execute("DELETE FROM assessment_drafts WHERE id = %s", (row["id"],))
            return None
    return _assessment_draft_from_row(row)


def save_assessment_draft(
    user_id: str,
    answers: dict[str, Any],
    current_step: int,
    *,
    version: int = 0,
    retention_days: int | None = None,
) -> dict[str, Any]:
    """Create or version a student's draft with optimistic concurrency."""
    record = _draft_storage_record(answers)
    current_step = max(0, min(current_step, 6))
    retention = (
        retention_days
        if retention_days is not None
        else get_settings().assessment_draft_retention_days
    )
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=max(retention, 1))

    with _connect() as connection:
        # Serialize drafts for the same account. This also prevents two first
        # saves from racing into the unique user_id constraint.
        connection.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
        row = connection.execute(
            """
            SELECT id, user_id, answers, current_step, version,
                   created_at, updated_at, expires_at
            FROM assessment_drafts
            WHERE user_id = %s
            FOR UPDATE
            """,
            (user_id,),
        ).fetchone()
        if row and row["expires_at"] <= now:
            connection.execute("DELETE FROM assessment_drafts WHERE id = %s", (row["id"],))
            row = None

        if row:
            current_version = int(row["version"])
            if version != current_version:
                raise AssessmentDraftConflictError(_assessment_draft_from_row(row) or {})
            draft_id = row["id"]
            next_version = current_version + 1
            connection.execute(
                """
                UPDATE assessment_drafts
                SET answers = %s,
                    current_step = %s,
                    version = %s,
                    updated_at = %s,
                    expires_at = %s
                WHERE id = %s
                """,
                (Jsonb(record), current_step, next_version, now, expires_at, draft_id),
            )
            created_at = row["created_at"]
        else:
            if version not in {0, 1}:
                raise AssessmentDraftConflictError({})
            draft_id = str(uuid4())
            next_version = 1
            created_at = now
            connection.execute(
                """
                INSERT INTO assessment_drafts (
                    id, user_id, answers, current_step, version,
                    created_at, updated_at, expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    draft_id,
                    user_id,
                    Jsonb(record),
                    current_step,
                    next_version,
                    created_at,
                    now,
                    expires_at,
                ),
            )

    return {
        "id": draft_id,
        "userId": user_id,
        "answers": record,
        "currentStep": current_step,
        "version": next_version,
        "createdAt": _iso_timestamp(created_at),
        "updatedAt": now.isoformat(),
        "expiresAt": expires_at.isoformat(),
    }


def delete_assessment_draft(user_id: str) -> bool:
    with _connect() as connection:
        result = connection.execute(
            "DELETE FROM assessment_drafts WHERE user_id = %s",
            (user_id,),
        )
    return result.rowcount > 0


def delete_expired_assessment_drafts() -> int:
    with _connect() as connection:
        result = connection.execute(
            "DELETE FROM assessment_drafts WHERE expires_at <= now()"
        )
    return result.rowcount


def _lock_current_generation_claim(
    connection,
    *,
    user_id: str,
    generation_job_id: str | None,
    claim_token: str | None,
) -> bool:
    """Serialize privacy deletion with writes and verify the current worker lease."""
    connection.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
    if generation_job_id is None:
        return True
    if claim_token is None:
        return False
    row = connection.execute(
        """
        SELECT 1
        FROM generation_jobs
        WHERE job_id = %s
          AND user_id = %s
          AND status = 'running'
          AND claim_token = %s
        FOR UPDATE
        """,
        (generation_job_id, user_id, claim_token),
    ).fetchone()
    return row is not None


def save_assessment_progress(
    response: AssessmentResponse,
    profile: CareerProfile,
    *,
    generation_job_id: str | None = None,
    claim_token: str | None = None,
) -> bool:
    response_record = _response_storage_record(response)
    response_payload = response.model_dump(mode="json")
    profile_record = _profile_storage_record(profile)

    with _connect() as connection:
        if not _lock_current_generation_claim(
            connection,
            user_id=response.userId,
            generation_job_id=generation_job_id,
            claim_token=claim_token,
        ):
            return False
        connection.execute(
            """
            INSERT INTO assessment_responses (
                id, user_id, grade, college_major, submitted_at, created_at, data
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                grade = EXCLUDED.grade,
                college_major = EXCLUDED.college_major,
                submitted_at = EXCLUDED.submitted_at,
                data = EXCLUDED.data
            """,
            (
                response.id,
                response.userId,
                response.grade,
                response.collegeMajor,
                response.submittedAt,
                response.createdAt,
                Jsonb(response_record),
            ),
        )
        connection.execute(
            """
            INSERT INTO assessment_scores (
                assessment_id, ability_scores, interest_scores
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (assessment_id) DO UPDATE SET
                ability_scores = EXCLUDED.ability_scores,
                interest_scores = EXCLUDED.interest_scores
            """,
            (
                response.id,
                Jsonb(response_payload["abilityScores"]),
                Jsonb(response_payload["interestScores"]),
            ),
        )
        connection.execute(
            "DELETE FROM assessment_choices WHERE assessment_id = %s",
            (response.id,),
        )
        for question_code in ASSESSMENT_LIST_FIELDS:
            for sort_order, value in enumerate(response_payload[question_code]):
                connection.execute(
                    """
                    INSERT INTO assessment_choices (
                        id, assessment_id, question_code, option_value, sort_order
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        f"{response.id}:{question_code}:{sort_order}",
                        response.id,
                        question_code,
                        value,
                        sort_order,
                    ),
                )
        connection.execute(
            """
            INSERT INTO career_profiles (
                id, user_id, response_id, model_name, prompt_version, created_at, data
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                model_name = EXCLUDED.model_name,
                prompt_version = EXCLUDED.prompt_version,
                data = EXCLUDED.data
            """,
            (
                profile.id,
                profile.userId,
                profile.responseId,
                profile.modelName,
                profile.promptVersion,
                profile.createdAt,
                Jsonb(profile_record),
            ),
        )
    return True


def _report_storage_record(report: CareerBlueprintReport) -> dict[str, Any]:
    record = report.model_dump(mode="json")
    record.pop("inputSnapshot", None)
    record.pop("accountDisplayName", None)
    return record


def _save_report_version(
    connection,
    report: CareerBlueprintReport,
    source: str,
    generation_job_id: str | None = None,
) -> None:
    row = connection.execute(
        """
        SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version
        FROM report_versions
        WHERE report_id = %s
        """,
        (report.id,),
    ).fetchone()
    connection.execute(
        """
        INSERT INTO report_versions (
            id, report_id, version_number, title, content, word_count,
            quality_status, source, created_at, created_by, generation_job_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (generation_job_id)
            WHERE generation_job_id IS NOT NULL
            DO NOTHING
        """,
        (
            str(uuid4()),
            report.id,
            row["next_version"],
            report.title,
            report.content,
            report.wordCount,
            report.qualityStatus,
            source,
            report.updatedAt,
            report.editedBy,
            generation_job_id,
        ),
    )


def save_report(
    report: CareerBlueprintReport,
    generation_job_id: str | None = None,
    *,
    claim_token: str | None = None,
) -> bool:
    record = _report_storage_record(report)
    with _connect() as connection:
        if not _lock_current_generation_claim(
            connection,
            user_id=report.userId,
            generation_job_id=generation_job_id,
            claim_token=claim_token,
        ):
            return False
        connection.execute(
            """
            INSERT INTO reports (
                id, user_id, response_id, profile_id, title, generation_status,
                quality_status, created_at, updated_at, edited_at, edited_by, data
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                generation_status = EXCLUDED.generation_status,
                quality_status = EXCLUDED.quality_status,
                updated_at = EXCLUDED.updated_at,
                edited_at = EXCLUDED.edited_at,
                edited_by = EXCLUDED.edited_by,
                data = EXCLUDED.data
            """,
            (
                report.id,
                report.userId,
                report.responseId,
                report.profileId,
                report.title,
                report.generationStatus,
                report.qualityStatus,
                report.createdAt,
                report.updatedAt,
                report.editedAt,
                report.editedBy,
                Jsonb(record),
            ),
        )
        _save_report_version(
            connection,
            report,
            "ai_generated",
            generation_job_id=generation_job_id,
        )
    return True


def find_report(report_id: str) -> CareerBlueprintReport | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT reports.data, users.display_name
            FROM reports
            LEFT JOIN users ON users.id = reports.user_id
            WHERE reports.id = %s
            """,
            (report_id,),
        ).fetchone()
    if not row:
        return None

    record = dict(row["data"])
    response = find_response(record["responseId"])
    profile = find_profile(record["profileId"])
    record["inputSnapshot"] = {
        "response": response.model_dump(mode="json") if response else None,
        "profile": profile.model_dump(mode="json") if profile else None,
    }
    record["accountDisplayName"] = row["display_name"] or None
    return CareerBlueprintReport.model_validate(record)


def find_response(response_id: str) -> AssessmentResponse | None:
    with _connect() as connection:
        response_row = connection.execute(
            "SELECT data FROM assessment_responses WHERE id = %s",
            (response_id,),
        ).fetchone()
        score_row = connection.execute(
            "SELECT ability_scores, interest_scores FROM assessment_scores WHERE assessment_id = %s",
            (response_id,),
        ).fetchone()
        choice_rows = connection.execute(
            """
            SELECT question_code, option_value, sort_order
            FROM assessment_choices
            WHERE assessment_id = %s
            ORDER BY question_code, sort_order
            """,
            (response_id,),
        ).fetchall()

    if not response_row or not score_row:
        return None

    payload = dict(response_row["data"])
    payload["abilityScores"] = score_row["ability_scores"]
    payload["interestScores"] = score_row["interest_scores"]
    for question_code in ASSESSMENT_LIST_FIELDS:
        payload[question_code] = [
            item["option_value"]
            for item in sorted(
                (
                    choice
                    for choice in choice_rows
                    if choice["question_code"] == question_code
                ),
                key=lambda item: item["sort_order"],
            )
        ]
    return AssessmentResponse.model_validate(payload)


def find_profile(profile_id: str) -> CareerProfile | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT data FROM career_profiles WHERE id = %s",
            (profile_id,),
        ).fetchone()
    return CareerProfile.model_validate(row["data"]) if row else None


def update_profile(profile: CareerProfile) -> None:
    with _connect() as connection:
        connection.execute(
            """
            UPDATE career_profiles
            SET model_name = %s, prompt_version = %s, data = %s
            WHERE id = %s
            """,
            (
                profile.modelName,
                profile.promptVersion,
                Jsonb(_profile_storage_record(profile)),
                profile.id,
            ),
        )


def _insert_admin_audit(
    connection,
    *,
    admin_id: str,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO admin_audit_logs (
            id, admin_id, action, target_type, target_id, created_at, details
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            str(uuid4()),
            admin_id,
            action,
            target_type,
            target_id,
            created_at or datetime.now(timezone.utc).isoformat(),
            Jsonb(details or {}),
        ),
    )


def update_report(report: CareerBlueprintReport) -> None:
    record = _report_storage_record(report)
    with _connect() as connection:
        previous = connection.execute(
            "SELECT title FROM reports WHERE id = %s",
            (report.id,),
        ).fetchone()
        if not previous:
            return

        connection.execute(
            """
            UPDATE reports
            SET title = %s,
                generation_status = %s,
                quality_status = %s,
                updated_at = %s,
                edited_at = %s,
                edited_by = %s,
                data = %s
            WHERE id = %s
            """,
            (
                report.title,
                report.generationStatus,
                report.qualityStatus,
                report.updatedAt,
                report.editedAt,
                report.editedBy,
                Jsonb(record),
                report.id,
            ),
        )
        source = "admin_edit" if report.editedBy else "ai_regenerated"
        _save_report_version(connection, report, source)

        if report.editedBy:
            _insert_admin_audit(
                connection,
                admin_id=report.editedBy,
                action="report.update",
                target_type="report",
                target_id=report.id,
                created_at=report.updatedAt,
                details={
                    "changedFields": ["title", "content"],
                    "qualityStatus": report.qualityStatus,
                },
            )


def save_feedback(feedback: ReportFeedback) -> None:
    record = feedback.model_dump(mode="json")
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO report_feedback (
                id, report_id, user_id, understanding_score, insight_score,
                action_score, recommend_score, created_at, data
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                feedback.id,
                feedback.reportId,
                feedback.userId,
                feedback.understandingScore,
                feedback.insightScore,
                feedback.actionScore,
                feedback.recommendScore,
                feedback.createdAt,
                Jsonb(record),
            ),
        )


def _iso_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _generation_job_from_row(row: dict[str, Any] | None) -> GenerationJobStatus | None:
    if not row:
        return None
    record = dict(row["data"])
    updated_at = _iso_timestamp(row.get("updated_at"))
    record.setdefault("createdAt", updated_at)
    record["updatedAt"] = updated_at
    return GenerationJobStatus.model_validate(record)


def save_generation_job(job: GenerationJobStatus) -> None:
    record = job.model_dump(mode="json")
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO generation_jobs (
                job_id, user_id, status, stage, created_at, data
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (job_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                status = EXCLUDED.status,
                stage = EXCLUDED.stage,
                data = EXCLUDED.data,
                updated_at = now()
            """,
            (
                job.jobId,
                job.userId,
                job.status,
                job.stage,
                job.createdAt or datetime.now(timezone.utc),
                Jsonb(record),
            ),
        )


def save_generation_job_if_user_idle(
    job: GenerationJobStatus,
    *,
    input_data: dict[str, Any] | None = None,
    daily_limit: int = 0,
    quota_day: date | None = None,
    quota_since: datetime | None = None,
    retention_days: int = 30,
) -> GenerationJobStatus | None:
    """Atomically reserve one user slot and persist the private generation input.

    ``input_data`` deliberately lives outside the public job JSON so polling the
    job endpoint can never return the questionnaire answers.
    """
    if not job.userId:
        save_generation_job(job)
        return None

    record = job.model_dump(mode="json")
    with _connect() as connection:
        connection.execute(
            """
            DELETE FROM generation_jobs
            WHERE status IN ('success', 'failed', 'cancelled')
              AND updated_at < %s
            """,
            (datetime.now(timezone.utc) - timedelta(days=max(retention_days, 1)),),
        )
        quota_user = connection.execute(
            """
            SELECT generation_quota_day, generation_quota_used
            FROM users
            WHERE id = %s
            FOR UPDATE
            """,
            (job.userId,),
        ).fetchone()
        active_row = connection.execute(
            """
            SELECT data, updated_at
            FROM generation_jobs
            WHERE user_id = %s
              AND status IN ('queued', 'running')
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (job.userId,),
        ).fetchone()
        if active_row:
            return _generation_job_from_row(active_row)

        current_quota_day = quota_day or datetime.now(timezone.utc).date()
        stored_quota_day = quota_user["generation_quota_day"] if quota_user else None
        if stored_quota_day == current_quota_day:
            used = int(quota_user["generation_quota_used"] or 0)
        else:
            # During a rolling upgrade, seed today's account counter from
            # existing job rows.  Afterwards the account counter remains
            # authoritative even when a student deletes report/job data.
            default_quota_since = datetime.now(timezone.utc).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            quota_row = connection.execute(
                """
                SELECT COUNT(*) AS used
                FROM generation_jobs
                WHERE user_id = %s AND created_at >= %s
                """,
                (job.userId, quota_since or default_quota_since),
            ).fetchone()
            used = int(quota_row["used"])
        if daily_limit > 0 and used >= daily_limit:
            raise GenerationQuotaStorageError(limit=daily_limit, used=used)

        connection.execute(
            """
            INSERT INTO generation_jobs (
                job_id, user_id, status, stage, created_at, input_data, data
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                job.jobId,
                job.userId,
                job.status,
                job.stage,
                job.createdAt or datetime.now(timezone.utc),
                Jsonb(_generation_input_storage_record(input_data))
                if input_data is not None
                else None,
                Jsonb(record),
            ),
        )
        connection.execute(
            """
            UPDATE users
            SET generation_quota_day = %s,
                generation_quota_used = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (
                current_quota_day,
                used + 1,
                datetime.now(timezone.utc).isoformat(),
                job.userId,
            ),
        )
    return None


def load_generation_job_input(job_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT input_data FROM generation_jobs WHERE job_id = %s",
            (job_id,),
        ).fetchone()
    if not row or row["input_data"] is None:
        return None
    return dict(row["input_data"])


def claim_generation_job(
    job_id: str,
    *,
    claim_token: str,
    lease_seconds: int,
) -> GenerationJobStatus | None:
    updates = {
        "status": "running",
        "stage": "preparing",
        "progress": 10,
        "message": "正在整理问卷答案和生成任务。",
        "error": None,
    }
    with _connect() as connection:
        row = connection.execute(
            """
            UPDATE generation_jobs
            SET status = 'running',
                stage = 'preparing',
                claim_token = %s,
                lease_expires_at = now() + (%s * interval '1 second'),
                updated_at = now(),
                data = jsonb_set(
                    data || %s,
                    '{attempts}',
                    to_jsonb(COALESCE((data->>'attempts')::integer, 0) + 1)
                )
            WHERE job_id = %s
              AND (
                  status = 'queued'
                  OR (
                      status = 'running'
                      AND (lease_expires_at IS NULL OR lease_expires_at <= now())
                  )
              )
            RETURNING data, updated_at
            """,
            (claim_token, max(lease_seconds, 1), Jsonb(updates), job_id),
        ).fetchone()
    return _generation_job_from_row(row)


def generation_job_retry_delay(job_id: str, default_seconds: int) -> float | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT status,
                   GREATEST(
                       EXTRACT(EPOCH FROM (lease_expires_at - now())),
                       0
                   ) AS retry_after
            FROM generation_jobs
            WHERE job_id = %s
            """,
            (job_id,),
        ).fetchone()
    if not row or row["status"] not in {"queued", "running"}:
        return None
    if row["status"] == "queued":
        return 0.1
    return max(float(row["retry_after"] or default_seconds), 0.1)


def renew_generation_job_lease(job_id: str, claim_token: str, lease_seconds: int) -> bool:
    with _connect() as connection:
        result = connection.execute(
            """
            UPDATE generation_jobs
            SET lease_expires_at = now() + (%s * interval '1 second')
            WHERE job_id = %s AND status = 'running' AND claim_token = %s
            """,
            (max(lease_seconds, 1), job_id, claim_token),
        )
    return result.rowcount == 1


def update_generation_job_conditionally(
    job_id: str,
    updates: dict[str, Any],
    *,
    expected_statuses: tuple[str, ...],
    claim_token: str | None = None,
    clear_private_state: bool = False,
) -> GenerationJobStatus | None:
    clauses = ["job_id = %s", "status = ANY(%s)"]
    where_params: list[Any] = [job_id, list(expected_statuses)]
    if claim_token is not None:
        clauses.append("claim_token = %s")
        where_params.append(claim_token)

    new_status = updates.get("status")
    new_stage = updates.get("stage")
    with _connect() as connection:
        row = connection.execute(
            f"""
            UPDATE generation_jobs
            SET status = COALESCE(%s, status),
                stage = COALESCE(%s, stage),
                updated_at = now(),
                data = data || %s,
                input_data = CASE WHEN %s THEN NULL ELSE input_data END,
                claim_token = CASE WHEN %s THEN NULL ELSE claim_token END,
                lease_expires_at = CASE WHEN %s THEN NULL ELSE lease_expires_at END
            WHERE {' AND '.join(clauses)}
            RETURNING data, updated_at
            """,
            (
                new_status,
                new_stage,
                Jsonb(updates),
                clear_private_state,
                clear_private_state,
                clear_private_state,
                *where_params,
            ),
        ).fetchone()
    return _generation_job_from_row(row)


def cancel_generation_job_record(job_id: str) -> GenerationJobStatus | None:
    return update_generation_job_conditionally(
        job_id,
        {
            "status": "cancelled",
            "stage": "cancelled",
            "message": "报告生成已取消。",
            "error": None,
        },
        expected_statuses=("queued", "running"),
        clear_private_state=True,
    )


def list_recoverable_generation_job_ids() -> list[str]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT job_id
            FROM generation_jobs
            WHERE status IN ('queued', 'running')
            ORDER BY created_at
            """
        ).fetchall()
    return [str(row["job_id"]) for row in rows]


def list_active_user_generation_job_ids(user_id: str) -> list[str]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT job_id
            FROM generation_jobs
            WHERE user_id = %s AND status IN ('queued', 'running')
            ORDER BY created_at
            """,
            (user_id,),
        ).fetchall()
    return [str(row["job_id"]) for row in rows]


def delete_expired_generation_jobs(retention_days: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(retention_days, 1))
    with _connect() as connection:
        result = connection.execute(
            """
            DELETE FROM generation_jobs
            WHERE status IN ('success', 'failed', 'cancelled')
              AND updated_at < %s
            """,
            (cutoff,),
        )
    return result.rowcount


def clear_expired_generation_quota_counters(current_day: date) -> int:
    """Clear account-level quota metadata after its local natural day ends."""
    with _connect() as connection:
        result = connection.execute(
            """
            UPDATE users
            SET generation_quota_day = NULL,
                generation_quota_used = 0,
                updated_at = %s
            WHERE generation_quota_day IS NOT NULL
              AND generation_quota_day < %s
            """,
            (datetime.now(timezone.utc).isoformat(), current_day),
        )
    return result.rowcount


def reserve_speech_quota(user_id: str, current_day: date, daily_limit: int) -> int:
    """Atomically reserve one transcription attempt for a user.

    The counter lives on the account so deleting business data cannot be used
    to bypass the daily limit.  A non-positive limit disables enforcement but
    still keeps the current day's usage available for operations checks.
    """
    with _connect() as connection:
        quota_user = connection.execute(
            """
            SELECT speech_quota_day, speech_quota_used
            FROM users
            WHERE id = %s
            FOR UPDATE
            """,
            (user_id,),
        ).fetchone()
        if not quota_user:
            raise RuntimeError("语音转写用户不存在。")

        used = (
            int(quota_user["speech_quota_used"] or 0)
            if quota_user["speech_quota_day"] == current_day
            else 0
        )
        if daily_limit > 0 and used >= daily_limit:
            raise SpeechQuotaStorageError(limit=daily_limit, used=used)

        next_used = used + 1
        connection.execute(
            """
            UPDATE users
            SET speech_quota_day = %s,
                speech_quota_used = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (
                current_day,
                next_used,
                datetime.now(timezone.utc).isoformat(),
                user_id,
            ),
        )
    return next_used


def clear_expired_speech_quota_counters(current_day: date) -> int:
    """Clear speech quota metadata after its configured local day ends."""
    with _connect() as connection:
        result = connection.execute(
            """
            UPDATE users
            SET speech_quota_day = NULL,
                speech_quota_used = 0,
                updated_at = %s
            WHERE speech_quota_day IS NOT NULL
              AND speech_quota_day < %s
            """,
            (datetime.now(timezone.utc).isoformat(), current_day),
        )
    return result.rowcount


def find_generation_job(job_id: str) -> GenerationJobStatus | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT data, updated_at FROM generation_jobs WHERE job_id = %s",
            (job_id,),
        ).fetchone()
    return _generation_job_from_row(row)


def get_user_generation_jobs(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT data, updated_at
            FROM generation_jobs
            WHERE user_id = %s
              AND status <> 'success'
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()

    return [
        job.model_dump(mode="json")
        for row in rows
        if (job := _generation_job_from_row(row)) is not None
    ]


def get_metrics() -> dict[str, Any]:
    with _connect() as connection:
        metrics = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM assessment_responses) AS assessment_count,
                (SELECT COUNT(*) FROM reports WHERE generation_status = 'success') AS report_success_count,
                (SELECT COUNT(*) FROM reports WHERE generation_status = 'failed') AS report_failed_count,
                (SELECT COUNT(*) FROM report_feedback) AS feedback_count,
                COALESCE(ROUND(AVG(understanding_score)::numeric, 1), 0) AS average_understanding_score,
                COALESCE(ROUND(AVG(insight_score)::numeric, 1), 0) AS average_insight_score,
                COALESCE(ROUND(AVG(action_score)::numeric, 1), 0) AS average_action_score,
                COALESCE(ROUND(AVG(recommend_score)::numeric, 1), 0) AS average_recommend_score
            FROM report_feedback
            """
        ).fetchone()
        low_score_rows = connection.execute(
            """
            SELECT report_id, MAX(created_at) AS latest_feedback_at
            FROM report_feedback
            WHERE LEAST(
                understanding_score,
                insight_score,
                action_score,
                recommend_score
            ) <= 2
            GROUP BY report_id
            ORDER BY latest_feedback_at DESC
            """
        ).fetchall()

    return {
        "assessmentCount": metrics["assessment_count"],
        "reportSuccessCount": metrics["report_success_count"],
        "reportFailedCount": metrics["report_failed_count"],
        "feedbackCount": metrics["feedback_count"],
        "averageUnderstandingScore": float(metrics["average_understanding_score"]),
        "averageInsightScore": float(metrics["average_insight_score"]),
        "averageActionScore": float(metrics["average_action_score"]),
        "averageRecommendScore": float(metrics["average_recommend_score"]),
        "lowScoreReports": [item["report_id"] for item in low_score_rows],
    }


def get_recent_reports(limit: int = 8) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT data
            FROM reports
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [dict(row["data"]) for row in rows]


def get_user_reports(user_id: str) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT data
            FROM reports
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()

    reports: list[dict[str, Any]] = []
    for row in rows:
        report = dict(row["data"])
        response = find_response(report["responseId"])
        report["inputSnapshot"] = {
            "response": response.model_dump(mode="json") if response else None,
        }
        reports.append(report)
    return reports


def get_admin_records() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT
                reports.data AS report,
                users.id AS user_id,
                users.username,
                users.display_name,
                assessment_responses.grade,
                assessment_responses.college_major,
                assessment_responses.submitted_at,
                assessment_responses.data AS assessment_data
            FROM reports
            LEFT JOIN users ON users.id = reports.user_id
            LEFT JOIN assessment_responses ON assessment_responses.id = reports.response_id
            ORDER BY reports.created_at DESC
            """
        ).fetchall()
        report_ids = [
            dict(row["report"]).get("id")
            for row in rows
            if row["report"]
        ]
        response_ids = [
            dict(row["report"]).get("responseId")
            for row in rows
            if row["report"]
        ]
        feedback_rows = []
        if report_ids:
            feedback_rows = connection.execute(
                """
                SELECT report_id, data
                FROM report_feedback
                WHERE report_id = ANY(%s::text[])
                ORDER BY created_at DESC
                """,
                (report_ids,),
            ).fetchall()
        confusion_choice_rows = []
        if response_ids:
            confusion_choice_rows = connection.execute(
                """
                SELECT assessment_id, option_value, sort_order
                FROM assessment_choices
                WHERE question_code = 'careerConfusions'
                  AND assessment_id = ANY(%s::text[])
                ORDER BY assessment_id, sort_order
                """,
                (response_ids,),
            ).fetchall()

    feedbacks_by_report: dict[str, list[dict[str, Any]]] = {}
    for feedback_row in feedback_rows:
        feedbacks_by_report.setdefault(feedback_row["report_id"], []).append(dict(feedback_row["data"]))

    confusions_by_response: dict[str, list[str]] = {}
    for choice_row in confusion_choice_rows:
        confusions_by_response.setdefault(choice_row["assessment_id"], []).append(choice_row["option_value"])

    records = []
    for row in rows:
        report = dict(row["report"])
        assessment_data = dict(row["assessment_data"] or {})
        response_id = report.get("responseId", "")
        student_name = assessment_data.get("studentName") or row["display_name"] or row["username"] or "未知用户"
        school = assessment_data.get("school") or ""
        student_number = assessment_data.get("studentNumber") or ""
        contact_info = assessment_data.get("contactInfo") or ""
        career_confusions = (
            confusions_by_response.get(response_id)
            or assessment_data.get("careerConfusions")
            or []
        )
        records.append(
            {
                "report": report,
                "student": {
                    "id": row["user_id"],
                    "username": row["username"] or "未知用户",
                    "displayName": student_name,
                    "school": school,
                    "studentNumber": student_number,
                    "contactInfo": contact_info,
                },
                "assessment": {
                    "educationStage": assessment_data.get("educationStage") or "",
                    "grade": row["grade"] or "",
                    "collegeMajor": row["college_major"] or "",
                    "careerConfusions": career_confusions,
                    "submittedAt": row["submitted_at"] or report["createdAt"],
                },
                "feedbacks": feedbacks_by_report.get(report["id"], []),
            }
        )
    return records


def delete_report_bundle(
    report_id: str,
    user_id: str,
    *,
    admin_id: str | None = None,
) -> bool:
    """Delete one report and data that is exclusively owned by that report.

    Ownership and deletion are checked in one transaction. Shared assessment or
    profile rows are preserved if another report still references them.
    """
    with _connect() as connection:
        connection.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
        row = connection.execute(
            """
            SELECT response_id, profile_id
            FROM reports
            WHERE id = %s AND user_id = %s
            FOR UPDATE
            """,
            (report_id, user_id),
        ).fetchone()
        if not row:
            return False

        response_id = row["response_id"]
        profile_id = row["profile_id"]
        connection.execute("DELETE FROM reports WHERE id = %s", (report_id,))
        connection.execute(
            """
            DELETE FROM generation_jobs
            WHERE user_id = %s
              AND (
                  data->>'reportId' = %s
                  OR data->>'responseId' = %s
              )
            """,
            (user_id, report_id, response_id),
        )
        connection.execute(
            """
            DELETE FROM career_profiles
            WHERE id = %s
              AND NOT EXISTS (SELECT 1 FROM reports WHERE profile_id = %s)
            """,
            (profile_id, profile_id),
        )
        connection.execute(
            """
            DELETE FROM assessment_responses
            WHERE id = %s
              AND user_id = %s
              AND NOT EXISTS (SELECT 1 FROM reports WHERE response_id = %s)
            """,
            (response_id, user_id, response_id),
        )
        if admin_id:
            _insert_admin_audit(
                connection,
                admin_id=admin_id,
                action="report.delete",
                target_type="report",
                target_id=report_id,
                details={"ownerUserId": user_id},
            )
    return True


def delete_user_business_data(user_id: str) -> dict[str, int]:
    """Delete a student's business records while preserving the login account."""
    with _connect() as connection:
        connection.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM assessment_responses WHERE user_id = %s) AS assessments,
                (SELECT COUNT(*) FROM career_profiles WHERE user_id = %s) AS profiles,
                (SELECT COUNT(*) FROM reports WHERE user_id = %s) AS reports,
                (SELECT COUNT(*) FROM report_feedback WHERE user_id = %s) AS feedbacks,
                (SELECT COUNT(*) FROM generation_jobs WHERE user_id = %s) AS generation_jobs,
                (SELECT COUNT(*) FROM assessment_drafts WHERE user_id = %s) AS assessment_drafts
            """,
            (user_id, user_id, user_id, user_id, user_id, user_id),
        ).fetchone()
        connection.execute("DELETE FROM generation_jobs WHERE user_id = %s", (user_id,))
        connection.execute("DELETE FROM report_feedback WHERE user_id = %s", (user_id,))
        connection.execute("DELETE FROM assessment_drafts WHERE user_id = %s", (user_id,))
        # Delete explicitly by owner as well as by cascade so malformed legacy
        # cross-links cannot leave personal records behind.
        connection.execute("DELETE FROM reports WHERE user_id = %s", (user_id,))
        connection.execute("DELETE FROM career_profiles WHERE user_id = %s", (user_id,))
        connection.execute("DELETE FROM assessment_responses WHERE user_id = %s", (user_id,))

    return {
        "assessments": int(counts["assessments"]),
        "profiles": int(counts["profiles"]),
        "reports": int(counts["reports"]),
        "feedbacks": int(counts["feedbacks"]),
        "generationJobs": int(counts["generation_jobs"]),
        # Older database adapters may not expose the newly added count while
        # the deletion itself is still safe and idempotent.
        "assessmentDrafts": int(counts.get("assessment_drafts", 0)),
    }


def record_admin_audit(
    admin_id: str,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    with _connect() as connection:
        _insert_admin_audit(
            connection,
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )


def get_admin_audit_logs(*, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    with _connect() as connection:
        total_row = connection.execute("SELECT COUNT(*) AS total FROM admin_audit_logs").fetchone()
        rows = connection.execute(
            """
            SELECT logs.id,
                   logs.admin_id,
                   users.display_name AS admin_display_name,
                   users.username AS admin_username,
                   logs.action,
                   logs.target_type,
                   logs.target_id,
                   logs.created_at,
                   logs.details
            FROM admin_audit_logs AS logs
            LEFT JOIN users ON users.id = logs.admin_id
            ORDER BY logs.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        ).fetchall()

    return {
        "total": int(total_row["total"]),
        "items": [
            {
                "id": row["id"],
                "adminId": row["admin_id"],
                "adminDisplayName": row["admin_display_name"] or row["admin_username"] or "未知管理员",
                "action": row["action"],
                "targetType": row["target_type"],
                "targetId": row["target_id"],
                "createdAt": row["created_at"],
                "details": dict(row["details"] or {}),
            }
            for row in rows
        ],
    }


def delete_expired_admin_audit_logs(retention_days: int = 180) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(retention_days, 1))
    with _connect() as connection:
        result = connection.execute(
            "DELETE FROM admin_audit_logs WHERE created_at::timestamptz < %s",
            (cutoff,),
        )
    return result.rowcount


def purge_stored_raw_model_outputs() -> int:
    """Remove legacy raw model responses after the structured profile is saved."""
    with _connect() as connection:
        result = connection.execute(
            """
            UPDATE career_profiles
            SET data = data - 'rawModelOutput'
            WHERE data ? 'rawModelOutput'
            """
        )
    return result.rowcount


def purge_non_persisted_assessment_fields() -> int:
    """Remove fields whose values are only needed during one generation request."""
    fields = list(ASSESSMENT_NON_PERSISTED_FIELDS)
    with _connect() as connection:
        result = connection.execute(
            """
            UPDATE assessment_responses
            SET data = data - %s::text[]
            WHERE data ?| %s::text[]
            """,
            (fields, fields),
        )
    return result.rowcount
