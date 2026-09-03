"""
Candidate Portal Router - Unified entry point.

All candidate-facing API routes are consolidated here.
Internal organization by domain:
- profile: /me, /profile, /profile/comprehensive, /avatar
- applications: /applications/*, /dashboard, /current-application
- cv: /cv-data, /builder-data, /cv-review, /upload-cv, /analyze
- interviews: /interviews/*, /reset-interview
- subscriptions: /plans, /upgrade, /subscription/usage, /invoices/*
- jobs: /jobs/matches, /jobs/{id}/apply
- qualifications: /qualifications/*
- extras: /badges, /talent-graph, /export, /invitations, /career/roadmap, /debug/*
"""

from fastapi import APIRouter

from . import (
    applications,
    cv,
    eeo,
    extras,
    interviews,
    jobs,
    profile,
    qualifications,
    saved_jobs,
    subscriptions,
)

router = APIRouter(prefix="/candidate", tags=["candidate"])

router.include_router(profile.router)
router.include_router(applications.router)
router.include_router(cv.router)
router.include_router(eeo.router)
router.include_router(interviews.router)
router.include_router(subscriptions.router)
router.include_router(jobs.router)
router.include_router(qualifications.router)
router.include_router(extras.router)
router.include_router(saved_jobs.router)

__all__ = ["router"]
