from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AbilityScores(BaseModel):
    logic: int = Field(ge=1, le=5)
    expression: int = Field(ge=1, le=5)
    spatialDesign: int = Field(ge=1, le=5)
    interpersonal: int = Field(ge=1, le=5)


class InterestScores(BaseModel):
    handsOn: int = Field(ge=1, le=5)
    research: int = Field(ge=1, le=5)
    creation: int = Field(ge=1, le=5)
    helping: int = Field(ge=1, le=5)
    leadership: int = Field(ge=1, le=5)
    detail: int = Field(ge=1, le=5)


class AssessmentResponseInput(BaseModel):
    studentName: str = ""
    school: str = ""
    studentNumber: str = ""
    contactInfo: str = ""
    educationStage: str = ""
    grade: str
    gender: str = ""
    collegeMajor: str
    hometown: Optional[str] = None
    mastersIntention: str
    mastersPlan: Optional[str] = None
    phdIntention: str
    phdPlan: Optional[str] = None
    doctoralCareerDirection: str = ""
    doctoralCareerOther: Optional[str] = None
    educationPathReasons: list[str]
    educationPathReasonOther: Optional[str] = None
    educationCertainty: int = Field(default=3, ge=1, le=5)
    fiveYearCity: str
    fiveYearIncome: str = ""
    fiveYearIndustry: str
    fiveYearRole: str
    fiveYearFamilyStatus: str
    fiveYearHousingPlan: str
    fiveYearHobbiesSkills: str
    tenYearCity: str
    tenYearIncome: str = ""
    tenYearIndustry: str
    tenYearRole: str
    tenYearFamilyStatus: str
    tenYearHousingPlan: str
    tenYearHobbiesSkills: str
    topValuesRanked: list[str]
    abilityScores: AbilityScores
    interestScores: InterestScores
    currentGpa: Optional[str] = None
    gpaScale: Optional[str] = None
    majorRank: Optional[str] = None
    majorTotal: Optional[str] = None
    englishCertificates: Optional[str] = None
    academicExperiences: Optional[str] = None
    failedCourseStatus: str = ""
    hasSecondMajor: str = ""
    secondMajorName: Optional[str] = None
    secondMajorProgress: Optional[str] = None
    secondMajorCareerInterest: Optional[str] = None
    hasTransferredMajor: str = ""
    originalMajorName: Optional[str] = None
    transferReason: Optional[str] = None
    originalMajorRetainedSkills: Optional[str] = None
    praisedTraits: list[str] = Field(default_factory=list)
    traitEvidence: Optional[str] = None
    immersiveActivities: Optional[str] = None
    favoriteKnowledgeAreas: Optional[str] = None
    selfDrivenActivities: Optional[str] = None
    preferredWorkStyle: list[str] = Field(default_factory=list)
    currentPreparations: list[str]
    currentPreparationOther: Optional[str] = None
    preparationDetails: Optional[str] = None
    missingResources: list[str]
    majorOutcomeAwareness: str
    targetJobAwareness: str
    jobInfoChannels: list[str]
    jobInfoChannelOther: Optional[str] = None
    healthEnergyStatus: str
    exerciseFrequency: Optional[str] = None
    longTermPersistence: int = Field(default=3, ge=1, le=5)
    executionStyle: str = ""
    executionCase: Optional[str] = None
    failureRecoveryTime: str = ""
    negativeFeedbackReaction: Optional[str] = None
    selfDoubtFrequency: str = ""
    problemSolvingStyle: str = ""
    supportNeed: str = ""
    highIntensityExperience: str = ""
    routineWorkTolerance: str = ""
    careerRiskPreference: str = ""
    careerConfusions: list[str]
    careerConfusionOther: Optional[str] = None
    mainConfusionText: Optional[str] = None
    userId: Optional[str] = None

    @field_validator("preferredWorkStyle", mode="before")
    @classmethod
    def normalize_preferred_work_style(cls, value):
        if isinstance(value, str):
            return [value] if value.strip() else []
        return value


class AssessmentResponse(AssessmentResponseInput):
    id: str
    userId: str
    submittedAt: str
    createdAt: str


class AssessmentSubmitResult(BaseModel):
    userId: str
    responseId: str
    profileId: str
    reportId: str
    generationStatus: str
