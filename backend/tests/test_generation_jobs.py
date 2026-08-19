from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, call, patch

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

from app.schemas.assessment import AssessmentResponseInput
from app.schemas.generation_job import GenerationJobStatus
from app.services import generation_jobs
from app.storage.json_db import GenerationQuotaStorageError


def make_job(status: str = "queued") -> GenerationJobStatus:
    return GenerationJobStatus(
        jobId="job-1",
        userId="user-1",
        status=status,
        stage=status,
        progress=5,
        message="test",
        createdAt="2026-07-30T00:00:00+00:00",
        updatedAt="2026-07-30T00:00:00+00:00",
    )


class GenerationJobReservationTest(TestCase):
    @patch.object(generation_jobs, "get_settings")
    @patch.object(generation_jobs, "save_generation_job_if_user_idle")
    def test_create_persists_input_and_applies_daily_quota(self, save_job, settings):
        settings.return_value = SimpleNamespace(
            report_generation_daily_limit=3,
            report_generation_quota_timezone="Asia/Shanghai",
            generation_job_retention_days=30,
        )
        save_job.return_value = None
        input_data = AssessmentResponseInput.model_construct(userId="user-1")

        created = generation_jobs.create_generation_job("user-1", input_data)

        self.assertEqual(created.status, "queued")
        kwargs = save_job.call_args.kwargs
        self.assertEqual(kwargs["daily_limit"], 3)
        self.assertEqual(kwargs["retention_days"], 30)
        self.assertEqual(kwargs["input_data"]["userId"], "user-1")
        self.assertIsNotNone(kwargs["quota_day"])

    @patch.object(generation_jobs, "get_settings")
    @patch.object(generation_jobs, "save_generation_job_if_user_idle")
    def test_quota_error_is_exposed_as_service_error(self, save_job, settings):
        settings.return_value = SimpleNamespace(
            report_generation_daily_limit=3,
            report_generation_quota_timezone="Asia/Shanghai",
            generation_job_retention_days=30,
        )
        save_job.side_effect = GenerationQuotaStorageError(limit=3, used=3)

        with self.assertRaises(generation_jobs.GenerationQuotaExceededError) as raised:
            generation_jobs.create_generation_job(
                "user-1",
                AssessmentResponseInput.model_construct(userId="user-1"),
            )

        self.assertEqual(raised.exception.limit, 3)
        self.assertEqual(raised.exception.used, 3)


class GenerationJobRecoveryTest(IsolatedAsyncioTestCase):
    @patch.object(generation_jobs, "get_settings")
    @patch.object(generation_jobs, "delete_expired_generation_jobs")
    @patch.object(generation_jobs, "list_recoverable_generation_job_ids")
    @patch.object(generation_jobs, "start_generation_job")
    def test_startup_recovers_all_durable_jobs(self, start, list_jobs, delete_old, settings):
        settings.return_value = SimpleNamespace(generation_job_retention_days=30)
        list_jobs.return_value = ["queued-job", "running-job"]

        count = generation_jobs.recover_generation_jobs()

        self.assertEqual(count, 2)
        delete_old.assert_called_once_with(30)
        self.assertEqual(
            start.call_args_list,
            [
                call("queued-job"),
                call("running-job"),
            ],
        )

    @patch.object(generation_jobs.asyncio, "sleep", new_callable=AsyncMock)
    @patch.object(generation_jobs, "generation_job_retry_delay")
    @patch.object(generation_jobs, "claim_generation_job")
    @patch.object(generation_jobs, "get_settings")
    async def test_running_job_waits_for_lease_then_is_reclaimed(
        self,
        settings,
        claim,
        retry_delay,
        sleep,
    ):
        settings.return_value = SimpleNamespace(
            generation_job_lease_seconds=300,
            generation_job_heartbeat_seconds=30,
        )
        claim.side_effect = [None, make_job("running")]
        retry_delay.return_value = 0.1

        recovered = await generation_jobs._claim_when_available("job-1", "new-owner")

        self.assertEqual(recovered.jobId, "job-1")
        self.assertEqual(claim.call_count, 2)
        sleep.assert_awaited_once()

    @patch.object(generation_jobs, "save_report")
    @patch.object(generation_jobs, "_update_running_job")
    @patch.object(generation_jobs, "_heartbeat", new_callable=AsyncMock)
    @patch.object(generation_jobs, "find_report")
    @patch.object(generation_jobs, "_claim_when_available", new_callable=AsyncMock)
    async def test_recovery_reuses_report_saved_before_status_commit(
        self,
        claim,
        find_report,
        _heartbeat,
        update_job,
        save_report,
    ):
        claimed = make_job("running").model_copy(update={"reportId": "report-1"})
        claim.return_value = claimed
        find_report.return_value = SimpleNamespace(
            id="report-1",
            generationStatus="success",
        )

        await generation_jobs.run_generation_job("job-1")

        save_report.assert_not_called()
        self.assertEqual(update_job.call_args.kwargs["status"], "success")
        self.assertTrue(update_job.call_args.kwargs["terminal"])


class GenerationJobCancellationTest(TestCase):
    @patch.object(generation_jobs, "ACTIVE_TASK_LOOPS", new_callable=dict)
    @patch.object(generation_jobs, "ACTIVE_TASKS", new_callable=dict)
    @patch.object(generation_jobs, "cancel_generation_job_record")
    @patch.object(generation_jobs, "find_generation_job")
    def test_cancel_commits_terminal_state_before_stopping_local_task(
        self,
        find_job,
        cancel_record,
        active_tasks,
        active_loops,
    ):
        find_job.return_value = make_job("running")
        cancelled = make_job("cancelled")
        cancel_record.return_value = cancelled
        task = Mock(spec=asyncio.Task)
        task.done.return_value = False
        loop = Mock()
        active_tasks["job-1"] = task
        active_loops["job-1"] = loop

        result = generation_jobs.cancel_generation_job("job-1")

        self.assertIs(result, cancelled)
        cancel_record.assert_called_once_with("job-1")
        loop.call_soon_threadsafe.assert_called_once_with(task.cancel)

    @patch.object(generation_jobs, "update_generation_job_conditionally")
    def test_success_update_requires_running_status_and_current_claim(self, update):
        update.return_value = None

        result = generation_jobs._update_running_job(
            "job-1",
            "worker-token",
            terminal=True,
            status="success",
            stage="completed",
        )

        self.assertIsNone(result)
        self.assertEqual(update.call_args.kwargs["expected_statuses"], ("running",))
        self.assertEqual(update.call_args.kwargs["claim_token"], "worker-token")
        self.assertTrue(update.call_args.kwargs["clear_private_state"])


if __name__ == "__main__":
    import unittest

    unittest.main()
