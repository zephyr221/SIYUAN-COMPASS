import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.assessments import router as assessments_router
from app.api.auth import router as auth_router
from app.api.feedback import router as feedback_router
from app.api.llm import router as llm_router
from app.api.privacy import router as privacy_router
from app.api.reports import router as reports_router
from app.api.speech import router as speech_router
from app.core.config import get_settings
from app.services.generation_jobs import recover_generation_jobs
from app.storage.json_db import (
    clear_expired_generation_quota_counters,
    clear_expired_speech_quota_counters,
    delete_expired_admin_audit_logs,
    delete_expired_assessment_drafts,
    delete_expired_generation_jobs,
    ensure_admin_account,
    ensure_storage,
    purge_non_persisted_assessment_fields,
    purge_stored_raw_model_outputs,
)

settings = get_settings()
logger = logging.getLogger(__name__)
DATA_MAINTENANCE_INTERVAL_SECONDS = 24 * 60 * 60
DATA_MAINTENANCE_TASK: asyncio.Task[None] | None = None


def run_data_maintenance() -> dict[str, int]:
    generation_quota_day = datetime.now(
        ZoneInfo(settings.report_generation_quota_timezone)
    ).date()
    speech_quota_day = datetime.now(ZoneInfo(settings.speech_quota_timezone)).date()
    result = {
        "generationJobs": delete_expired_generation_jobs(
            settings.generation_job_retention_days
        ),
        "assessmentDrafts": delete_expired_assessment_drafts(),
        "adminAuditLogs": delete_expired_admin_audit_logs(
            retention_days=settings.admin_audit_retention_days
        ),
        "rawModelOutputs": purge_stored_raw_model_outputs(),
        "nonPersistedAssessmentFields": purge_non_persisted_assessment_fields(),
        "generationQuotaCounters": clear_expired_generation_quota_counters(
            generation_quota_day
        ),
        "speechQuotaCounters": clear_expired_speech_quota_counters(speech_quota_day),
    }
    logger.info(
        "data maintenance completed: generation_jobs=%d assessment_drafts=%d admin_audit_logs=%d "
        "raw_model_outputs=%d non_persisted_assessment_records=%d "
        "generation_quota_counters=%d speech_quota_counters=%d",
        result["generationJobs"],
        result["assessmentDrafts"],
        result["adminAuditLogs"],
        result["rawModelOutputs"],
        result["nonPersistedAssessmentFields"],
        result["generationQuotaCounters"],
        result["speechQuotaCounters"],
    )
    return result


async def _run_daily_data_maintenance() -> None:
    while True:
        await asyncio.sleep(DATA_MAINTENANCE_INTERVAL_SECONDS)
        try:
            await asyncio.to_thread(run_data_maintenance)
        except Exception:
            logger.exception("daily data maintenance failed")


async def startup() -> None:
    global DATA_MAINTENANCE_TASK
    ensure_storage()
    ensure_admin_account()
    run_data_maintenance()
    recover_generation_jobs()
    DATA_MAINTENANCE_TASK = asyncio.create_task(_run_daily_data_maintenance())


async def shutdown() -> None:
    global DATA_MAINTENANCE_TASK
    if DATA_MAINTENANCE_TASK:
        DATA_MAINTENANCE_TASK.cancel()
        with suppress(asyncio.CancelledError):
            await DATA_MAINTENANCE_TASK
        DATA_MAINTENANCE_TASK = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await startup()
    try:
        yield
    finally:
        await shutdown()


app = FastAPI(
    title="大学生生涯规划智能小助手 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api")
app.include_router(assessments_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(speech_router, prefix="/api")
app.include_router(feedback_router, prefix="/api")
app.include_router(privacy_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(llm_router, prefix="/api")
