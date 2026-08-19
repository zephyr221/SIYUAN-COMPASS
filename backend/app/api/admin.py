from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.data_privacy import contains_obvious_contact_details
from app.schemas.report import AdminReportUpdate
from app.services.auth import require_admin
from app.services.report_quality_check import check_report_quality, count_chineseish_words
from app.storage.json_db import (
    find_report,
    find_response,
    get_admin_audit_logs,
    get_admin_records,
    get_metrics,
    get_recent_reports,
    record_admin_audit,
    update_report,
)

router = APIRouter(tags=["admin"])


@router.get("/admin/metrics")
def admin_metrics(admin=Depends(require_admin)):
    record_admin_audit(admin["id"], "admin.metrics.read", "report_collection", "metrics")
    return {**get_metrics(), "recentReports": get_recent_reports()}


@router.get("/admin/records")
def admin_records(admin=Depends(require_admin)):
    record_admin_audit(admin["id"], "admin.records.read", "report_collection", "all")
    return {"records": get_admin_records()}


@router.get("/admin/assessments/{response_id}")
def admin_assessment(response_id: str, admin=Depends(require_admin)):
    response = find_response(response_id)
    if not response:
        raise HTTPException(status_code=404, detail={"error": "问卷不存在"})
    record_admin_audit(admin["id"], "assessment.read", "assessment", response_id)
    return response.model_dump(mode="json")


@router.get("/admin/audit-logs")
def admin_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin=Depends(require_admin),
):
    record_admin_audit(admin["id"], "admin.audit.read", "audit_log", "all")
    return get_admin_audit_logs(limit=limit, offset=offset)


@router.put("/admin/reports/{report_id}")
def edit_report(
    report_id: str,
    input_data: AdminReportUpdate,
    admin=Depends(require_admin),
):
    report = find_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail={"error": "报告不存在"})
    if contains_obvious_contact_details(f"{input_data.title}\n{input_data.content}"):
        raise HTTPException(
            status_code=400,
            detail={"error": "报告标题或正文包含疑似手机号、邮箱或长数字标识，请脱敏后再保存。"},
        )

    quality = check_report_quality(input_data.content)
    report.title = input_data.title.strip()
    report.content = input_data.content.strip()
    report.wordCount = count_chineseish_words(report.content)
    report.qualityStatus = quality["status"]
    report.errorMessage = "；".join(quality["warnings"]) or None
    report.updatedAt = datetime.now(timezone.utc).isoformat()
    report.editedAt = report.updatedAt
    report.editedBy = admin["id"]
    update_report(report)
    return report
