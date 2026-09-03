"""Domain enumerations for ATS models."""

import enum


class ApplicationType(str, enum.Enum):
    JOB = "job"
    CAMPAIGN = "campaign"
    AI_INTERVIEW = "ai_interview"
    REFERRAL = "referral"
    IMPORT = "import"
    MANUAL = "manual"
