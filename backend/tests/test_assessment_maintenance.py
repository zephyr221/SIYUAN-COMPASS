from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, Response

from app.api import assessments
from app.services import generation_jobs


class AssessmentMaintenanceTest(unittest.TestCase):
    def settings(self, active: bool):
        return SimpleNamespace(
            assessment_submission_maintenance=active,
            assessment_submission_maintenance_message="报告生成服务正在维护，请稍后查看。",
        )

    def test_public_status_exposes_message(self):
        response = Response()
        with patch.object(assessments, "get_settings", return_value=self.settings(True)):
            self.assertEqual(
                assessments.get_assessment_maintenance(response),
                {
                    "active": True,
                    "message": "报告生成服务正在维护，请稍后查看。",
                },
            )
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_submission_is_rejected_during_maintenance(self):
        with patch.object(assessments, "get_settings", return_value=self.settings(True)):
            with self.assertRaises(HTTPException) as raised:
                assessments._require_submission_available()

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.headers, {"Retry-After": "3600"})
        self.assertTrue(raised.exception.detail["maintenance"])

    def test_submission_remains_available_when_switch_is_off(self):
        with patch.object(assessments, "get_settings", return_value=self.settings(False)):
            assessments._require_submission_available()

    def test_draft_write_is_rejected_during_maintenance(self):
        with patch.object(assessments, "get_settings", return_value=self.settings(True)):
            with self.assertRaises(HTTPException) as raised:
                assessments.upsert_assessment_draft(None, user={"id": "user-1"})

        self.assertEqual(raised.exception.status_code, 503)

    def test_maintenance_disables_recovery_of_accepted_jobs(self):
        with patch.object(
            generation_jobs,
            "get_settings",
            return_value=SimpleNamespace(
                generation_job_retention_days=30,
                assessment_submission_maintenance=True,
            ),
        ), patch.object(
            generation_jobs,
            "delete_expired_generation_jobs",
        ), patch.object(
            generation_jobs,
            "list_recoverable_generation_job_ids",
            return_value=["accepted-job"],
        ), patch.object(generation_jobs, "start_generation_job") as start:
            recovered = generation_jobs.recover_generation_jobs()

        self.assertEqual(recovered, 0)
        start.assert_not_called()

    def test_recovery_remains_available_when_maintenance_is_off(self):
        with patch.object(
            generation_jobs,
            "get_settings",
            return_value=SimpleNamespace(
                generation_job_retention_days=30,
                assessment_submission_maintenance=False,
            ),
        ), patch.object(
            generation_jobs,
            "delete_expired_generation_jobs",
        ), patch.object(
            generation_jobs,
            "list_recoverable_generation_job_ids",
            return_value=["accepted-job"],
        ), patch.object(generation_jobs, "start_generation_job") as start:
            recovered = generation_jobs.recover_generation_jobs()

        self.assertEqual(recovered, 1)
        start.assert_called_once_with("accepted-job")


if __name__ == "__main__":
    unittest.main()
