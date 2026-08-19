from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class GenerationJobCreated(BaseModel):
    jobId: str
    status: Literal["queued"]


class GenerationJobStatus(BaseModel):
    jobId: str
    status: Literal["queued", "running", "success", "failed", "cancelled"]
    stage: str
    progress: int = Field(ge=0, le=100)
    message: str
    userId: Optional[str] = None
    responseId: Optional[str] = None
    profileId: Optional[str] = None
    reportId: Optional[str] = None
    generationStatus: Optional[str] = None
    error: Optional[str] = None
    attempts: int = Field(default=0, ge=0)
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
