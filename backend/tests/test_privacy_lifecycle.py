from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from types import ModuleType, SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import Mock, patch

from fastapi import HTTPException

try:
    import psycopg  # noqa: F401
except ModuleNotFoundError:
    psycopg_module = ModuleType("psycopg")
    psycopg_module.connect = Mock()
    rows_module = ModuleType("psycopg.rows")
    rows_module.dict_row = object()
    types_module = ModuleType("psycopg.types")
    json_module = ModuleType("psycopg.types.json")
    json_module.Jsonb = lambda value: value
    sys.modules["psycopg"] = psycopg_module
    sys.modules["psycopg.rows"] = rows_module
    sys.modules["psycopg.types"] = types_module
    sys.modules["psycopg.types.json"] = json_module

from app import main
from app.api import admin, privacy, reports
from app.schemas.generation_job import GenerationJobStatus
from app.storage import json_db


class Dumpable:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def model_dump(self, **_kwargs):
        return dict(self.payload)


@contextmanager
def fake_connection(connection):
    yield connection


class DataMinimizationTest(TestCase):
    def test_assessment_storage_excludes_every_no_store_field(self):
        payload = {
            "abilityScores": {},
            "interestScores": {},
            "grade": "大二",
            **{field: [] for field in json_db.ASSESSMENT_LIST_FIELDS},
            **{
                field: f"secret-{field}"
                for field in json_db.ASSESSMENT_NON_PERSISTED_FIELDS
            },
        }

        stored = json_db._response_storage_record(Dumpable(payload))

        self.assertEqual(stored["grade"], "大二")
        for field in json_db.ASSESSMENT_NON_PERSISTED_FIELDS:
            self.assertNotIn(field, stored)

    def test_newly_collected_fields_remain_in_assessment_snapshot(self):
        payload = {
            "abilityScores": {},
            "interestScores": {},
            "grade": "大二",
            "studentName": "张同学",
            "studentNumber": "20260001",
            "contactInfo": "student@example.invalid",
            "gender": "不便透露",
            "fiveYearIncome": "暂不确定",
            "tenYearIncome": "希望逐步提高",
            **{field: [] for field in json_db.ASSESSMENT_LIST_FIELDS},
        }

        stored = json_db._response_storage_record(Dumpable(payload))

        for field in [
            "studentName",
            "studentNumber",
            "contactInfo",
            "gender",
            "fiveYearIncome",
            "tenYearIncome",
        ]:
            self.assertEqual(stored[field], payload[field])

    def test_profile_storage_never_keeps_raw_model_output(self):
        stored = json_db._profile_storage_record(
            Dumpable({"summary": "structured", "rawModelOutput": "raw response"})
        )

        self.assertEqual(stored, {"summary": "structured"})

    def test_durable_job_input_excludes_every_no_store_field(self):
        payload = {
            "userId": "user-1",
            "grade": "大二",
            "mainConfusionText": "隐私姓名希望回访 privacy@example.invalid，也可联系 139 0013 8000 或 alt@example.invalid",
            "studentName": "隐私姓名",
            "contactInfo": "privacy@example.invalid",
            **{
                field: f"secret-{field}"
                for field in json_db.ASSESSMENT_NON_PERSISTED_FIELDS
                if field not in {"studentName", "contactInfo"}
            },
        }

        stored = json_db._generation_input_storage_record(payload)

        self.assertEqual(stored["userId"], "user-1")
        self.assertEqual(stored["grade"], "大二")
        self.assertEqual(
            stored["mainConfusionText"],
            "[已脱敏]希望回访 [已脱敏]，也可联系 [已脱敏] 或 [已脱敏]",
        )
        self.assertEqual(stored["studentName"], "隐私姓名")
        self.assertEqual(stored["contactInfo"], "privacy@example.invalid")
        for field in json_db.ASSESSMENT_NON_PERSISTED_FIELDS:
            self.assertNotIn(field, stored)

    def test_legacy_assessment_cleanup_uses_the_same_field_allowlist(self):
        result = Mock(rowcount=4)
        connection = Mock()
        connection.execute.return_value = result

        with patch.object(json_db, "_connect", return_value=fake_connection(connection)):
            changed = json_db.purge_non_persisted_assessment_fields()

        self.assertEqual(changed, 4)
        params = connection.execute.call_args.args[1]
        self.assertEqual(params[0], list(json_db.ASSESSMENT_NON_PERSISTED_FIELDS))
        self.assertEqual(params[1], list(json_db.ASSESSMENT_NON_PERSISTED_FIELDS))

    def test_assessment_draft_storage_removes_unknown_and_no_store_fields(self):
        stored = json_db._draft_storage_record(
            {
                "collegeMajor": "计算机",
                "educationCertainty": 5,
                "unexpected": "must not persist",
                "userId": "attacker-user",
            }
        )

        self.assertEqual(stored, {"collegeMajor": "计算机"})

    def test_draft_save_locks_owner_and_uses_versioned_upsert(self):
        connection = Mock()
        missing_draft = Mock()
        missing_draft.fetchone.return_value = None
        connection.execute.side_effect = [Mock(), missing_draft, Mock()]
        with patch.object(json_db, "_connect", return_value=fake_connection(connection)), patch.object(
            json_db, "get_settings", return_value=SimpleNamespace(assessment_draft_retention_days=30)
        ):
            draft = json_db.save_assessment_draft(
                "user-1", {"collegeMajor": "计算机", "userId": "spoof"}, 2
            )

        self.assertEqual(draft["userId"], "user-1")
        self.assertEqual(draft["version"], 1)
        self.assertEqual(draft["answers"], {"collegeMajor": "计算机"})
        self.assertIn("FOR UPDATE", connection.execute.call_args_list[1].args[0])

    def test_draft_save_rejects_stale_version(self):
        connection = Mock()
        existing_draft = Mock()
        existing_draft.fetchone.return_value = {
            "id": "draft-1",
            "user_id": "user-1",
            "answers": {"collegeMajor": "计算机"},
            "current_step": 2,
            "version": 4,
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=5),
            "updated_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
        }
        connection.execute.side_effect = [Mock(), existing_draft]
        with patch.object(json_db, "_connect", return_value=fake_connection(connection)), patch.object(
            json_db, "get_settings", return_value=SimpleNamespace(assessment_draft_retention_days=30)
        ):
            with self.assertRaises(json_db.AssessmentDraftConflictError) as raised:
                json_db.save_assessment_draft("user-1", {"collegeMajor": "错误覆盖"}, 2, version=3)

        self.assertEqual(raised.exception.current["version"], 4)


class PrivacyDeletionTest(TestCase):
    def test_single_report_delete_cascades_and_audits_admin_in_one_transaction(self):
        statements: list[str] = []
        connection = Mock()

        def execute(statement, _params=None):
            normalized = " ".join(statement.split())
            statements.append(normalized)
            result = Mock()
            if "SELECT response_id, profile_id FROM reports" in normalized:
                result.fetchone.return_value = {
                    "response_id": "response-1",
                    "profile_id": "profile-1",
                }
            return result

        connection.execute.side_effect = execute
        with patch.object(json_db, "_connect", return_value=fake_connection(connection)):
            deleted = json_db.delete_report_bundle(
                "report-1",
                "student-1",
                admin_id="admin-1",
            )

        self.assertTrue(deleted)
        all_sql = "\n".join(statements)
        self.assertIn("DELETE FROM reports WHERE id = %s", all_sql)
        self.assertIn("DELETE FROM generation_jobs", all_sql)
        self.assertIn("DELETE FROM career_profiles", all_sql)
        self.assertIn("DELETE FROM assessment_responses", all_sql)
        self.assertIn("INSERT INTO admin_audit_logs", all_sql)

    def test_business_data_deletion_preserves_account_and_deletes_owned_rows(self):
        statements: list[str] = []
        connection = Mock()

        def execute(statement, _params=None):
            normalized = " ".join(statement.split())
            statements.append(normalized)
            result = Mock()
            if "SELECT COUNT(*)" in normalized:
                result.fetchone.return_value = {
                    "assessments": 2,
                    "profiles": 2,
                    "reports": 1,
                    "feedbacks": 1,
                    "generation_jobs": 1,
                    "assessment_drafts": 1,
                }
            return result

        connection.execute.side_effect = execute
        with patch.object(json_db, "_connect", return_value=fake_connection(connection)):
            deleted = json_db.delete_user_business_data("user-1")

        self.assertEqual(deleted["reports"], 1)
        all_sql = "\n".join(statements)
        for table in [
            "generation_jobs",
            "report_feedback",
            "assessment_drafts",
            "reports",
            "career_profiles",
            "assessment_responses",
        ]:
            self.assertIn(f"DELETE FROM {table}", all_sql)
        self.assertNotIn("DELETE FROM users", all_sql)
        self.assertIn("SELECT id FROM users WHERE id = %s FOR UPDATE", all_sql)


class GenerationQuotaPersistenceTest(TestCase):
    def test_account_counter_is_incremented_in_the_job_reservation_transaction(self):
        connection = Mock()
        quota_user = Mock()
        quota_user.fetchone.return_value = {
            "generation_quota_day": date(2026, 7, 30),
            "generation_quota_used": 2,
        }
        active_job = Mock()
        active_job.fetchone.return_value = None
        connection.execute.side_effect = [Mock(), quota_user, active_job, Mock(), Mock()]
        job = GenerationJobStatus(
            jobId="job-1",
            userId="user-1",
            status="queued",
            stage="queued",
            progress=5,
            message="queued",
            createdAt="2026-07-30T00:00:00+00:00",
            updatedAt="2026-07-30T00:00:00+00:00",
        )

        with patch.object(json_db, "_connect", return_value=fake_connection(connection)):
            result = json_db.save_generation_job_if_user_idle(
                job,
                input_data={"userId": "user-1"},
                daily_limit=3,
                quota_day=date(2026, 7, 30),
            )

        self.assertIsNone(result)
        quota_update = connection.execute.call_args_list[-1]
        self.assertIn("UPDATE users", quota_update.args[0])
        self.assertEqual(quota_update.args[1][0], date(2026, 7, 30))
        self.assertEqual(quota_update.args[1][1], 3)
        self.assertEqual(quota_update.args[1][3], "user-1")

    def test_expired_account_quota_counter_is_cleared(self):
        connection = Mock()
        connection.execute.return_value = Mock(rowcount=2)

        with patch.object(json_db, "_connect", return_value=fake_connection(connection)):
            changed = json_db.clear_expired_generation_quota_counters(
                date(2026, 7, 31)
            )

        self.assertEqual(changed, 2)
        statement, params = connection.execute.call_args.args
        self.assertIn("generation_quota_day = NULL", statement)
        self.assertEqual(params[1], date(2026, 7, 31))

    def test_generation_write_is_rejected_after_its_claim_is_deleted(self):
        connection = Mock()
        missing_claim = Mock()
        missing_claim.fetchone.return_value = None
        connection.execute.side_effect = [Mock(), missing_claim]

        allowed = json_db._lock_current_generation_claim(
            connection,
            user_id="user-1",
            generation_job_id="job-1",
            claim_token="worker-1",
        )

        self.assertFalse(allowed)

    @patch.object(privacy, "delete_user_business_data", return_value={})
    @patch.object(privacy, "cancel_generation_job")
    @patch.object(
        privacy,
        "list_active_user_generation_job_ids",
        return_value=["job-1", "job-2"],
    )
    def test_privacy_delete_cancels_active_workers_first(
        self,
        _list_jobs,
        cancel_job,
        delete_data,
    ):
        privacy.delete_my_business_data({"id": "user-1", "role": "student"})

        self.assertEqual(cancel_job.call_count, 2)
        delete_data.assert_called_once_with("user-1")


class AdminAuditTest(TestCase):
    @patch.object(reports, "record_admin_audit")
    @patch.object(reports, "find_report")
    def test_generic_admin_report_read_is_audited(self, find_report, record_audit):
        find_report.return_value = SimpleNamespace(userId="student-1")

        reports._get_report_or_404(
            "report-1",
            {"id": "admin-1", "role": "admin"},
        )

        record_audit.assert_called_once_with(
            "admin-1",
            "report.read",
            "report",
            "report-1",
        )

    @patch.object(reports, "delete_report_bundle")
    @patch.object(reports, "_get_report_or_404")
    def test_admin_report_delete_passes_actor_for_atomic_audit(self, get_report, delete):
        get_report.return_value = SimpleNamespace(id="report-1", userId="student-1")
        delete.return_value = True

        reports.delete_report(
            "report-1",
            {"id": "admin-1", "role": "admin"},
        )

        delete.assert_called_once_with(
            "report-1",
            "student-1",
            admin_id="admin-1",
        )

    @patch.object(admin, "get_recent_reports", return_value=[])
    @patch.object(admin, "get_metrics", return_value={})
    @patch.object(admin, "record_admin_audit")
    def test_metrics_sensitive_read_is_audited(self, record_audit, _metrics, _recent):
        admin.admin_metrics({"id": "admin-1", "role": "admin"})

        record_audit.assert_called_once_with(
            "admin-1",
            "admin.metrics.read",
            "report_collection",
            "metrics",
        )

    @patch.object(admin, "find_report", return_value=SimpleNamespace())
    def test_admin_cannot_save_obvious_contact_details_in_report(self, _find_report):
        with self.assertRaises(HTTPException) as raised:
            admin.edit_report(
                "report-1",
                SimpleNamespace(title="报告", content="请联系 13800138000"),
                {"id": "admin-1", "role": "admin"},
            )

        self.assertEqual(raised.exception.status_code, 400)


class MaintenanceLifecycleTest(TestCase):
    @patch.object(main, "delete_expired_assessment_drafts", return_value=7)
    @patch.object(main, "clear_expired_speech_quota_counters", return_value=6)
    @patch.object(main, "clear_expired_generation_quota_counters", return_value=5)
    @patch.object(main, "purge_non_persisted_assessment_fields", return_value=4)
    @patch.object(main, "purge_stored_raw_model_outputs", return_value=3)
    @patch.object(main, "delete_expired_admin_audit_logs", return_value=2)
    @patch.object(main, "delete_expired_generation_jobs", return_value=1)
    def test_maintenance_wires_all_retention_cleanups(
        self,
        generation_jobs,
        audit_logs,
        raw_outputs,
        assessment_fields,
        quota_counters,
        speech_quota_counters,
        assessment_drafts,
    ):
        result = main.run_data_maintenance()

        generation_jobs.assert_called_once_with(main.settings.generation_job_retention_days)
        assessment_drafts.assert_called_once_with()
        audit_logs.assert_called_once_with(
            retention_days=main.settings.admin_audit_retention_days
        )
        raw_outputs.assert_called_once_with()
        assessment_fields.assert_called_once_with()
        quota_counters.assert_called_once()
        speech_quota_counters.assert_called_once()
        self.assertEqual(
            result,
            {
                "generationJobs": 1,
                "assessmentDrafts": 7,
                "adminAuditLogs": 2,
                "rawModelOutputs": 3,
                "nonPersistedAssessmentFields": 4,
                "generationQuotaCounters": 5,
                "speechQuotaCounters": 6,
            },
        )


class MaintenanceShutdownTest(IsolatedAsyncioTestCase):
    @patch.object(main, "recover_generation_jobs")
    @patch.object(main, "run_data_maintenance")
    @patch.object(main, "ensure_admin_account")
    @patch.object(main, "ensure_storage")
    async def test_startup_cleans_once_and_schedules_daily_loop(
        self,
        ensure_storage,
        ensure_admin,
        run_maintenance,
        recover_jobs,
    ):
        scheduled = Mock()

        def create_task(coroutine):
            coroutine.close()
            return scheduled

        with patch.object(main.asyncio, "create_task", side_effect=create_task):
            await main.startup()

        ensure_storage.assert_called_once_with()
        ensure_admin.assert_called_once_with()
        run_maintenance.assert_called_once_with()
        recover_jobs.assert_called_once_with()
        self.assertIs(main.DATA_MAINTENANCE_TASK, scheduled)
        self.assertEqual(main.DATA_MAINTENANCE_INTERVAL_SECONDS, 24 * 60 * 60)
        main.DATA_MAINTENANCE_TASK = None

    async def test_shutdown_cancels_daily_maintenance_task(self):
        class CancelledTask:
            cancelled = False

            def cancel(self):
                self.cancelled = True

            def __await__(self):
                async def wait_for_cancel():
                    raise __import__("asyncio").CancelledError

                return wait_for_cancel().__await__()

        task = CancelledTask()
        with patch.object(main, "DATA_MAINTENANCE_TASK", task):
            await main.shutdown()
            self.assertTrue(task.cancelled)


if __name__ == "__main__":
    import unittest

    unittest.main()
