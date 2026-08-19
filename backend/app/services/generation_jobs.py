from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.schemas.assessment import AssessmentResponse, AssessmentResponseInput
from app.schemas.generation_job import GenerationJobStatus
from app.services.profile_analyzer import ProfileAnalysisError, analyze_career_profile
from app.services.report_generator import ReportGenerationError, generate_report
from app.storage.json_db import (
    GenerationQuotaStorageError,
    cancel_generation_job_record,
    claim_generation_job,
    delete_expired_generation_jobs,
    find_generation_job,
    find_report,
    find_user,
    generation_job_retry_delay,
    list_recoverable_generation_job_ids,
    load_generation_job_input,
    renew_generation_job_lease,
    save_assessment_progress,
    save_generation_job_if_user_idle,
    save_report,
    update_generation_job_conditionally,
)

ACTIVE_TASKS: dict[str, asyncio.Task[None]] = {}
ACTIVE_TASK_LOOPS: dict[str, asyncio.AbstractEventLoop] = {}


class ActiveGenerationJobError(RuntimeError):
    def __init__(self, active_job: GenerationJobStatus) -> None:
        self.active_job = active_job
        super().__init__("该账号已有报告正在生成中")


class GenerationQuotaExceededError(RuntimeError):
    def __init__(self, *, limit: int, used: int) -> None:
        self.limit = limit
        self.used = used
        super().__init__(f"今日报告生成次数已用完（{used}/{limit}）")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_generation_job(
    user_id: str,
    input_data: AssessmentResponseInput,
) -> GenerationJobStatus:
    job_id = str(uuid4())
    now = now_iso()
    job = GenerationJobStatus(
        jobId=job_id,
        status="queued",
        stage="queued",
        progress=5,
        message="问卷已接收，等待开始分析。",
        userId=user_id,
        createdAt=now,
        updatedAt=now,
    )
    settings = get_settings()
    quota_timezone = ZoneInfo(settings.report_generation_quota_timezone)
    quota_now = datetime.now(quota_timezone)
    quota_since = quota_now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    ).astimezone(timezone.utc)
    try:
        active_job = save_generation_job_if_user_idle(
            job,
            input_data=input_data.model_dump(mode="json"),
            daily_limit=max(settings.report_generation_daily_limit, 0),
            quota_day=quota_now.date(),
            quota_since=quota_since,
            retention_days=settings.generation_job_retention_days,
        )
    except GenerationQuotaStorageError as error:
        raise GenerationQuotaExceededError(limit=error.limit, used=error.used) from error
    if active_job:
        raise ActiveGenerationJobError(active_job)
    return job


def get_generation_job(job_id: str) -> GenerationJobStatus | None:
    return find_generation_job(job_id)


def _task_finished(job_id: str, task: asyncio.Task[None]) -> None:
    if ACTIVE_TASKS.get(job_id) is task:
        ACTIVE_TASKS.pop(job_id, None)
        ACTIVE_TASK_LOOPS.pop(job_id, None)


def start_generation_job(job_id: str) -> None:
    existing = ACTIVE_TASKS.get(job_id)
    if existing and not existing.done():
        return
    loop = asyncio.get_running_loop()
    task = loop.create_task(run_generation_job(job_id))
    ACTIVE_TASKS[job_id] = task
    ACTIVE_TASK_LOOPS[job_id] = loop
    task.add_done_callback(lambda finished: _task_finished(job_id, finished))


def recover_generation_jobs() -> int:
    """Resume durable jobs and remove old terminal status records on startup."""
    settings = get_settings()
    delete_expired_generation_jobs(settings.generation_job_retention_days)
    job_ids = list_recoverable_generation_job_ids()
    for job_id in job_ids:
        start_generation_job(job_id)
    return len(job_ids)


def cancel_generation_job(job_id: str) -> GenerationJobStatus | None:
    current = find_generation_job(job_id)
    if not current:
        return None
    if current.status not in {"queued", "running"}:
        return current

    cancelled = cancel_generation_job_record(job_id)
    if not cancelled:
        return find_generation_job(job_id)

    task = ACTIVE_TASKS.get(job_id)
    loop = ACTIVE_TASK_LOOPS.get(job_id)
    if task and loop and not task.done():
        loop.call_soon_threadsafe(task.cancel)
    return cancelled


async def _claim_when_available(job_id: str, claim_token: str) -> GenerationJobStatus | None:
    settings = get_settings()
    while True:
        claimed = claim_generation_job(
            job_id,
            claim_token=claim_token,
            lease_seconds=settings.generation_job_lease_seconds,
        )
        if claimed:
            return claimed
        retry_after = generation_job_retry_delay(
            job_id,
            settings.generation_job_lease_seconds,
        )
        if retry_after is None:
            return None
        await asyncio.sleep(
            min(
                retry_after + 0.05,
                max(settings.generation_job_heartbeat_seconds, 1),
            )
        )


async def _heartbeat(job_id: str, claim_token: str) -> None:
    settings = get_settings()
    interval = max(
        1,
        min(settings.generation_job_heartbeat_seconds, settings.generation_job_lease_seconds // 2),
    )
    while True:
        await asyncio.sleep(interval)
        if not renew_generation_job_lease(
            job_id,
            claim_token,
            settings.generation_job_lease_seconds,
        ):
            return


def _update_running_job(
    job_id: str,
    claim_token: str,
    *,
    terminal: bool = False,
    **updates: object,
) -> GenerationJobStatus | None:
    return update_generation_job_conditionally(
        job_id,
        dict(updates),
        expected_statuses=("running",),
        claim_token=claim_token,
        clear_private_state=terminal,
    )


def _require_job_update(
    job_id: str,
    claim_token: str,
    **updates: object,
) -> GenerationJobStatus:
    updated = _update_running_job(job_id, claim_token, **updates)
    if not updated:
        raise asyncio.CancelledError
    return updated


async def run_generation_job(job_id: str) -> None:
    claim_token = str(uuid4())
    heartbeat: asyncio.Task[None] | None = None
    try:
        claimed = await _claim_when_available(job_id, claim_token)
        if not claimed:
            return
        heartbeat = asyncio.create_task(_heartbeat(job_id, claim_token))

        # A crash can happen after the report transaction commits but before the
        # final job transition. Reuse that committed result instead of generating
        # a second report/version.
        if claimed.reportId:
            saved_report = find_report(claimed.reportId)
            if saved_report:
                _update_running_job(
                    job_id,
                    claim_token,
                    terminal=True,
                    status="success",
                    stage="completed",
                    progress=100,
                    message="生涯报告生成完成。",
                    reportId=saved_report.id,
                    generationStatus=saved_report.generationStatus,
                )
                return

        raw_input = load_generation_job_input(job_id)
        if raw_input is None:
            _update_running_job(
                job_id,
                claim_token,
                terminal=True,
                status="failed",
                stage="failed",
                message="生成任务缺少问卷数据。",
                error="generation job input is missing",
            )
            return
        input_data = AssessmentResponseInput.model_validate(raw_input)

        user = find_user(input_data.userId or "")
        if not user:
            raise RuntimeError("登录用户不存在")
        now = now_iso()
        payload = input_data.model_dump()
        payload.pop("userId", None)
        response = AssessmentResponse(
            **payload,
            id=claimed.responseId or str(uuid4()),
            userId=user["id"],
            submittedAt=now,
            createdAt=now,
        )
        _require_job_update(job_id, claim_token, userId=user["id"], responseId=response.id)

        def profile_progress(stage: str, progress: int, message: str) -> None:
            _require_job_update(
                job_id,
                claim_token,
                stage=stage,
                progress=progress,
                message=message,
            )

        try:
            profile = await analyze_career_profile(response, progress_callback=profile_progress)
        except ProfileAnalysisError as error:
            _update_running_job(
                job_id,
                claim_token,
                terminal=True,
                status="failed",
                stage="profile_failed",
                message="用户画像生成失败。",
                error=str(error),
            )
            return

        if claimed.profileId:
            profile.id = claimed.profileId
        _require_job_update(
            job_id,
            claim_token,
            profileId=profile.id,
            stage="profile_complete",
            progress=55,
            message="结构化用户画像已生成，正在准备生涯报告。",
        )
        if not save_assessment_progress(
            response,
            profile,
            generation_job_id=job_id,
            claim_token=claim_token,
        ):
            raise asyncio.CancelledError

        def report_progress(stage: str, progress: int, message: str) -> None:
            _require_job_update(
                job_id,
                claim_token,
                stage=stage,
                progress=progress,
                message=message,
            )

        try:
            report = await generate_report(response, profile, progress_callback=report_progress)
        except ReportGenerationError as error:
            _update_running_job(
                job_id,
                claim_token,
                terminal=True,
                status="failed",
                stage="report_failed",
                message="生涯报告生成失败。",
                error=str(error),
            )
            return

        if claimed.reportId:
            report.id = claimed.reportId
        _require_job_update(
            job_id,
            claim_token,
            stage="saving",
            progress=95,
            message="报告已通过校验，正在保存结果。",
            reportId=report.id,
        )
        if not save_report(
            report,
            generation_job_id=job_id,
            claim_token=claim_token,
        ):
            raise asyncio.CancelledError
        _update_running_job(
            job_id,
            claim_token,
            terminal=True,
            status="success",
            stage="completed",
            progress=100,
            message="生涯报告生成完成。",
            reportId=report.id,
            generationStatus=report.generationStatus,
        )
    except asyncio.CancelledError:
        # User cancellation already made a conditional terminal transition.
        # Process shutdown leaves the lease in place so another worker can recover it.
        raise
    except Exception as error:
        _update_running_job(
            job_id,
            claim_token,
            terminal=True,
            status="failed",
            stage="failed",
            message="生成流程发生异常。",
            error=str(error),
        )
    finally:
        if heartbeat:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
