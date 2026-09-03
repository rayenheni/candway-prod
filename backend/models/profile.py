"""Backward-compat re-export — profile models moved to evaluation/profile.py."""

from backend.models.evaluation.profile import (  # noqa: F401
    AdminProfile,
    CandidateProfile,
    RecruiterProfile,
)
