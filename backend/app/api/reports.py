from fastapi import APIRouter, Depends, HTTPException, Query

from app.services.auth import require_user
from app.storage.json_db import (
    delete_report_bundle,
    find_report,
    get_user_generation_jobs,
    get_user_reports,
    record_admin_audit,
)

router = APIRouter(tags=["reports"])


def _get_report_or_404(report_id: str, user):
    report = find_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail={"error": "报告不存在"})
    if user["role"] != "admin" and report.userId != user["id"]:
        raise HTTPException(status_code=403, detail={"error": "无权查看该报告"})
    if user["role"] == "admin":
        record_admin_audit(user["id"], "report.read", "report", report_id)
    return report


@router.get("/reports")
def get_report_by_query(
    report_id: str = Query(alias="reportId"),
    user=Depends(require_user),
):
    return _get_report_or_404(report_id, user)


@router.get("/reports/mine")
def get_my_reports(user=Depends(require_user)):
    return {
        "reports": get_user_reports(user["id"]),
        "jobs": get_user_generation_jobs(user["id"]),
    }


@router.get("/reports/{report_id}")
def get_report(report_id: str, user=Depends(require_user)):
    return _get_report_or_404(report_id, user)


@router.delete("/reports/{report_id}")
def delete_report(report_id: str, user=Depends(require_user)) -> dict[str, object]:
    report = _get_report_or_404(report_id, user)
    deleted = delete_report_bundle(
        report.id,
        report.userId,
        admin_id=user["id"] if user["role"] == "admin" else None,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail={"error": "报告不存在或已被删除"})
    return {
        "message": "报告、历史版本和反馈已删除；不再被其他报告使用的关联问卷与画像也已清除。",
        "reportId": report.id,
    }


def _legacy_regeneration_disabled(report_id: str, user) -> None:
    _get_report_or_404(report_id, user)
    raise HTTPException(
        status_code=410,
        detail={
            "error": "该重新生成入口已停用，请从“我的报告”选择“修改问卷重新生成”，以使用可恢复任务和每日配额。"
        },
    )


@router.post("/reports/regenerate")
def regenerate_report_by_query(
    report_id: str = Query(alias="reportId"),
    user=Depends(require_user),
):
    return _legacy_regeneration_disabled(report_id, user)


@router.post("/reports/{report_id}/regenerate")
def regenerate_report(report_id: str, user=Depends(require_user)):
    return _legacy_regeneration_disabled(report_id, user)
