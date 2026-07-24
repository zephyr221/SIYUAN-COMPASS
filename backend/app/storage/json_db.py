from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Literal
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.core.config import get_settings
from app.schemas.assessment import AssessmentResponse
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

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE,
    display_name TEXT,
    password_hash TEXT,
    auth_source TEXT NOT NULL DEFAULT 'local',
    role TEXT NOT NULL DEFAULT 'student',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_source TEXT NOT NULL DEFAULT 'local';

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
    created_by TEXT
);

CREATE TABLE IF NOT EXISTS generation_jobs (
    job_id TEXT PRIMARY KEY,
    user_id TEXT,
    status TEXT NOT NULL,
    stage TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    data JSONB NOT NULL
);

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
CREATE INDEX IF NOT EXISTS idx_career_profiles_response_id
    ON career_profiles(response_id);
CREATE INDEX IF NOT EXISTS idx_reports_user_id_created_at
    ON reports(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_reports_created_at
    ON reports(created_at);
CREATE INDEX IF NOT EXISTS idx_report_feedback_report_id
    ON report_feedback(report_id);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_user_status_updated_at
    ON generation_jobs(user_id, status, updated_at);
"""


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


def upsert_jaccount_user(*, username: str, display_name: str, is_admin: bool) -> dict[str, Any]:
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
                role = EXCLUDED.role,
                updated_at = EXCLUDED.updated_at
            RETURNING *
            """,
            (
                str(uuid4()),
                normalized,
                display_name.strip() or normalized,
                "admin" if is_admin else "student",
                now,
                now,
            ),
        ).fetchone()
    user = _user_from_row(row)
    if not user:
        raise RuntimeError("jAccount 用户写入失败")
    return user


def _response_storage_record(response: AssessmentResponse) -> dict[str, Any]:
    record = response.model_dump(mode="json")
    record.pop("abilityScores")
    record.pop("interestScores")
    for question_code in ASSESSMENT_LIST_FIELDS:
        record.pop(question_code)
    return record


def save_assessment_progress(response: AssessmentResponse, profile: CareerProfile) -> None:
    response_record = _response_storage_record(response)
    response_payload = response.model_dump(mode="json")
    profile_record = profile.model_dump(mode="json")

    with _connect() as connection:
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


def _report_storage_record(report: CareerBlueprintReport) -> dict[str, Any]:
    record = report.model_dump(mode="json")
    record.pop("inputSnapshot", None)
    record.pop("accountDisplayName", None)
    return record


def _save_report_version(connection, report: CareerBlueprintReport, source: str) -> None:
    row = connection.execute(
        "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version FROM report_versions WHERE report_id = %s",
        (report.id,),
    ).fetchone()
    connection.execute(
        """
        INSERT INTO report_versions (
            id, report_id, version_number, title, content, word_count,
            quality_status, source, created_at, created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        ),
    )


def save_report(report: CareerBlueprintReport) -> None:
    record = _report_storage_record(report)
    with _connect() as connection:
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
        _save_report_version(connection, report, "ai_generated")


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
                Jsonb(profile.model_dump(mode="json")),
                profile.id,
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
            connection.execute(
                """
                INSERT INTO admin_audit_logs (
                    id, admin_id, action, target_type, target_id, created_at, details
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid4()),
                    report.editedBy,
                    "report.update",
                    "report",
                    report.id,
                    report.updatedAt,
                    Jsonb(
                        {
                            "previousTitle": previous["title"],
                            "newTitle": report.title,
                        }
                    ),
                ),
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
            INSERT INTO generation_jobs (job_id, user_id, status, stage, data)
            VALUES (%s, %s, %s, %s, %s)
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
                Jsonb(record),
            ),
        )


def save_generation_job_if_user_idle(job: GenerationJobStatus) -> GenerationJobStatus | None:
    if not job.userId:
        save_generation_job(job)
        return None

    record = job.model_dump(mode="json")
    with _connect() as connection:
        connection.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (job.userId,))
        active_row = connection.execute(
            """
            SELECT data, updated_at
            FROM generation_jobs
            WHERE user_id = %s
              AND status IN ('queued', 'running')
              AND updated_at >= now() - interval '30 minutes'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (job.userId,),
        ).fetchone()
        if active_row:
            return _generation_job_from_row(active_row)

        connection.execute(
            """
            INSERT INTO generation_jobs (job_id, user_id, status, stage, data)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                job.jobId,
                job.userId,
                job.status,
                job.stage,
                Jsonb(record),
            ),
        )
    return None


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
