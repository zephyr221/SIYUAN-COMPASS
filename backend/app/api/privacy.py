from fastapi import APIRouter, Depends, HTTPException

from app.services.auth import require_user
from app.services.generation_jobs import cancel_generation_job
from app.storage.json_db import (
    delete_user_business_data,
    list_active_user_generation_job_ids,
)

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.delete("/my-data")
def delete_my_business_data(user=Depends(require_user)) -> dict[str, object]:
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail={"error": "管理员账号不能使用学生数据清除功能"})

    for job_id in list_active_user_generation_job_ids(user["id"]):
        cancel_generation_job(job_id)
    deleted = delete_user_business_data(user["id"])
    return {
        "message": "你的未提交草稿、问卷、画像、报告、版本、反馈和生成任务已清除；登录账号、当日报告生成次数和语音转写次数计数仍保留，计数会在自然日结束后清零。",
        "deleted": deleted,
    }
