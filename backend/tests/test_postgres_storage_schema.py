from pathlib import Path
import unittest


STORAGE_SOURCE = Path("app/storage/json_db.py").read_text(encoding="utf-8")
ADMIN_API_SOURCE = Path("app/api/admin.py").read_text(encoding="utf-8")


class PostgresStorageSchemaTest(unittest.TestCase):
    def test_postgres_schema_contains_expected_tables(self):
        for table in [
            "users",
            "assessment_responses",
            "assessment_scores",
            "assessment_choices",
            "assessment_drafts",
            "career_profiles",
            "reports",
            "report_versions",
            "generation_jobs",
            "report_feedback",
            "admin_audit_logs",
        ]:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", STORAGE_SOURCE)

    def test_assessment_list_fields_are_normalized_choices(self):
        expected_fields = (
            "educationPathReasons",
            "topValuesRanked",
            "praisedTraits",
            "currentPreparations",
            "missingResources",
            "jobInfoChannels",
            "careerConfusions",
        )
        for field in expected_fields:
            self.assertIn(field, STORAGE_SOURCE)

    def test_generation_jobs_have_active_user_guard(self):
        self.assertIn("idx_generation_jobs_user_status_updated_at", STORAGE_SOURCE)
        self.assertIn("save_generation_job_if_user_idle", STORAGE_SOURCE)
        self.assertIn("FOR UPDATE", STORAGE_SOURCE)

    def test_daily_quota_counter_survives_business_data_deletion(self):
        self.assertIn("generation_quota_day", STORAGE_SOURCE)
        self.assertIn("generation_quota_used", STORAGE_SOURCE)
        self.assertIn("speech_quota_day", STORAGE_SOURCE)
        self.assertIn("speech_quota_used", STORAGE_SOURCE)
        self.assertIn("UPDATE users", STORAGE_SOURCE)

    def test_admin_records_include_report_feedbacks(self):
        self.assertIn("feedbacks_by_report", STORAGE_SOURCE)
        self.assertIn('"feedbacks"', STORAGE_SOURCE)

    def test_admin_records_include_career_confusion_choices(self):
        self.assertIn("confusions_by_response", STORAGE_SOURCE)
        self.assertIn("question_code = 'careerConfusions'", STORAGE_SOURCE)

    def test_admin_can_fetch_assessment_detail(self):
        self.assertIn('/admin/assessments/{response_id}', ADMIN_API_SOURCE)
        self.assertIn("find_response", ADMIN_API_SOURCE)

    def test_report_lookup_includes_account_display_name(self):
        self.assertIn("LEFT JOIN users ON users.id = reports.user_id", STORAGE_SOURCE)
        self.assertIn('record["accountDisplayName"]', STORAGE_SOURCE)

    def test_jaccount_admin_role_is_managed_locally(self):
        self.assertIn("def set_jaccount_user_role", STORAGE_SOURCE)
        self.assertIn("role = users.role", STORAGE_SOURCE)
    def test_assessment_drafts_are_account_scoped_and_expiring(self):
        self.assertIn("user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE", STORAGE_SOURCE)
        self.assertIn("expires_at TIMESTAMPTZ NOT NULL", STORAGE_SOURCE)
        self.assertIn("AssessmentDraftConflictError", STORAGE_SOURCE)
        self.assertIn("WHERE user_id = %s", STORAGE_SOURCE)


if __name__ == "__main__":
    unittest.main()
