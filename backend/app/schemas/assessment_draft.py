from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AssessmentDraftUpsert(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    currentStep: int = Field(default=0, ge=0, le=6)
    version: int = Field(default=0, ge=0)


class AssessmentDraft(BaseModel):
    id: str
    userId: str
    answers: dict[str, Any]
    currentStep: int = Field(ge=0, le=6)
    version: int = Field(ge=1)
    createdAt: str
    updatedAt: str
    expiresAt: str


class AssessmentDraftEnvelope(BaseModel):
    draft: AssessmentDraft | None


class AssessmentDraftDeleteResult(BaseModel):
    deleted: bool
