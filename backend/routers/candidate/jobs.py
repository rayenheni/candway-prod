import json
import logging
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.database import Application, CvDocument, Job, Rubric, User
from backend.dependencies import get_current_user, get_db
from backend.enums import canonicalize_status
from backend.models.ats.types import ApplicationType
from backend.profile_helpers import (
    get_user_company_name,
    get_user_email,
    get_user_headline,
    get_user_name,
    get_user_phone,
    get_user_skills,
)
from backend.routers.candidate.cv import _load_builder_data, _synthesize_cv_text
from backend.services.application_service import (
    ApplicationService,
    normalize_application_source,
)
router = APIRouter(tags=["candidate"])

logger = logging.getLogger(__name__)


class ApplyRequest(BaseModel):
    source: Optional[str] = None
    # Optional explicit CV selection (see GET /candidate/cv-documents).
    # When set, the candidate's chosen CV document is attached instead of
    # auto-deriving the CV text from the most recent application.
    cv_document_id: Optional[int] = None


def _invitations_for_user_predicate(current_user: User):
    """Return a SQLAlchemy filter clause that returns ONLY the
    invitations that ``current_user`` is allowed to act on.

    P1-09 IDOR fix: the previous implementation filtered by
    ``Application.email == current_user.email`` alone, which
    allowed a malicious user to register with a victim's email
    (or change their own email to match) and then read or
    decline the victim's recruiter invitations. We now require
    one of two conditions:

    1. The invitation is already bound to this user via
       ``Application.user_id`` — the safe, intended path.
    2. The invitation has no ``user_id`` yet (the candidate
       hasn't registered) AND the candidate's email is
       verified AND the email matches exactly. This is the
       "claim an unlinked invitation" path; the email must be
       verified so a user who later adds the victim's email to
       their account cannot grab the invitation.

    Unverified-email users see no invitations — they must
    verify their email first, which is the correct UX.
    """
    email_verified = bool(getattr(current_user, "email_verified", False))
    email = (current_user.email or "").strip().lower()
    clauses = [Application.user_id == current_user.id]
    if email and email_verified:
        clauses.append(
            and_(
                Application.user_id.is_(None),
                Application.email == email,
            )
        )
    return or_(*clauses)


@router.get("/invitations")
def fetch_candidate_priority_invitations(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    from backend.database import BatchJob

    apps = (
        db.query(Application)
        .filter(
            Application.status.in_(["imported", "invited"]),
            _invitations_for_user_predicate(current_user),
        )
        .all()
    )
    results = []
    bound = False
    for app in apps:
        # P1-09 IDOR fix: opportunistically bind unlinked
        # invitations to the current user so the next access
        # uses the user_id path (faster + safer). Only do this
        # when the email is verified.
        if (
            app.user_id is None
            and bool(getattr(current_user, "email_verified", False))
            and (app.email or "").strip().lower()
            == (current_user.email or "").strip().lower()
        ):
            app.user_id = current_user.id
            db.add(app)
            bound = True
        campaign_name = "Direct Invitation"
        company_name = "Candway AI"
        if app.batch_id:
            batch = db.query(BatchJob).filter(BatchJob.id == app.batch_id).first()
            if batch:
                campaign_name = batch.title
                if batch.recruiter and get_user_company_name(batch.recruiter):
                    company_name = get_user_company_name(batch.recruiter)
        results.append(
            {
                "app_id": app.id,
                "role": app.declared_role or "General Role",
                "campaign": campaign_name,
                "company": company_name,
                "created_at": app.created_at.isoformat(),
                "status": canonicalize_status(app.status),
            }
        )
    if bound:
        db.commit()
    return results


class InvitationAction(BaseModel):
    application_id: int
    reason: Optional[str] = None


@router.post("/invitations/decline")
def decline_invitation(
    payload: InvitationAction,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Candidate-initiated decline of a recruiter invitation.

    Bug U-03: the candidate dashboard surfaced ``imported`` and
    ``invited`` applications as items the candidate "needs to
    respond to" but offered no way to decline. The status was
    trapped in ``imported/invited`` forever, the recruiter never
    learned the candidate had refused, and the dashboard list
    grew unbounded. This endpoint writes the new status and
    notifies the recruiter (best-effort).

    P1-09 IDOR fix: ``Application.email == current_user.email``
    is no longer sufficient — see
    :func:`_invitations_for_user_predicate`. A user who changes
    their email to a victim's now cannot read or decline the
    victim's invitations.
    """
    app = (
        db.query(Application)
        .filter(
            Application.id == payload.application_id,
            Application.status.in_(["imported", "invited"]),
            _invitations_for_user_predicate(current_user),
        )
        .first()
    )
    if not app:
        raise HTTPException(
            status_code=404,
            detail="Invitation not found or already actioned",
        )

    from backend.database import AuditLog

    app.status = "rejected"
    # Bug U-07: write the structured decline metadata to dedicated
    # columns so the recruiter can query / filter / display it
    # without parsing the recruiter_notes blob. We still set
    # recruiter_notes for backwards-compat with the audit-history
    # view (any saved page referencing the old string still
    # renders), but the new columns are the source of truth.
    app.declined_at = datetime.now(UTC)
    app.decline_reason = (payload.reason or "").strip() or None
    app.decline_initiated_by = "candidate"
    app.recruiter_notes = (
        "Candidate declined invitation."
        + (f" Reason: {payload.reason}" if payload.reason else "")
    ).strip()
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="invitation_declined",
            target_id=str(app.id),
            details=f"Declined invitation: {app.declared_role or 'unknown role'}. "
            f"Reason: {payload.reason or 'none provided'}",
            ip_address="candidate",
        )
    )
    db.commit()

    # Best-effort recruiter notification. We do not surface a 5xx
    # to the candidate if the notification fails.
    try:
        from backend.notifications import notify_user

        if app.batch_id and app.assigned_to:
            notify_user(
                user_id=app.assigned_to,
                message=(
                    f"{get_user_name(current_user) or get_user_email(current_user)} declined your invitation"
                    f" for the {app.declared_role or 'role'} position."
                ),
                title="Invitation declined",
                level="info",
                notification_type="invitation_declined",
                related_type="application",
                related_id=app.id,
                db_session=db,
            )
    except Exception as notif_err:  # noqa: BLE001
        logger.warning(
            f"Failed to notify recruiter for declined invitation {app.id}: {notif_err}"
        )

    return {
        "message": "Invitation declined",
        "application_id": app.id,
    }


@router.get("/jobs/matches")
def get_job_matches(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    applied_job_ids = set(
        db.query(Application.job_id)
        .filter(Application.user_id == current_user.id, Application.job_id.isnot(None))
        .all()
    )
    applied_job_ids = {jid[0] for jid in applied_job_ids}

    latest_app = (
        db.query(Application)
        .filter(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
        .first()
    )
    target_role = (
        latest_app.declared_role
        if latest_app
        else (get_user_headline(current_user) or "General")
    )
    user_skills = (
        set(get_user_skills(current_user).lower().split(","))
        if get_user_skills(current_user)
        else set()
    )

    if latest_app and latest_app.analysis_json:
        try:
            analysis = json.loads(latest_app.analysis_json)
            cv_skills = analysis.get("skills", []) or analysis.get("matched_skills", [])
            if isinstance(cv_skills, list):
                user_skills.update(s.lower().strip() for s in cv_skills if s)
        except Exception:
            pass

    query = db.query(Job).filter(Job.is_active)

    if target_role:
        term = f"%{target_role}%"
        matches = query.filter(Job.title.ilike(term)).limit(limit).all()
        if len(matches) < 5:
            others = query.limit(limit).all()
            seen = {m.id for m in matches}
            for o in others:
                if o.id not in seen:
                    matches.append(o)
                    if len(matches) >= limit:
                        break
        jobs = matches
    else:
        jobs = query.order_by(Job.created_at.desc()).limit(limit).all()

    def _compute_match_score(job: Job, user_skills: set, target_role: str) -> int:
        if not job.required_skills:
            return 50

        try:
            job_skills = set(s.lower().strip() for s in json.loads(job.required_skills))
        except Exception:
            job_skills = set(s.lower().strip() for s in job.required_skills.split(","))

        if not job_skills:
            return 50

        overlap = len(user_skills.intersection(job_skills))
        total = len(job_skills)

        skill_score = int((overlap / total) * 70) if total > 0 else 0

        role_bonus = (
            25 if (target_role and target_role.lower() in job.title.lower()) else 0
        )

        title_keywords = ["senior", "junior", "lead", "manager", "intern", "entry"]
        title_bonus = 5 if any(kw in job.title.lower() for kw in title_keywords) else 0

        return min(100, skill_score + role_bonus + title_bonus)

    return [
        {
            "id": j.id,
            "title": j.title,
            "company": j.company_name,
            "location": j.location,
            "type": j.type,
            "salary_range": j.salary_range,
            "match_score": _compute_match_score(j, user_skills, target_role),
            "posted_at": j.created_at.strftime("%Y-%m-%d") if j.created_at else None,
            "already_applied": j.id in applied_job_ids,
            "description": j.description,
            "required_skills": (
                json.loads(j.required_skills)
                if (j.required_skills and j.required_skills.strip().startswith("["))
                else [s.strip() for s in j.required_skills.split(",")]
            )
            if j.required_skills
            else [],
        }
        for j in jobs
    ]


@router.get("/jobs/{job_id}")
def get_job_detail(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id, Job.is_active).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    already_applied = bool(
        db.query(Application.id)
        .filter(Application.user_id == current_user.id, Application.job_id == job_id)
        .first()
    )

    existing_app = (
        db.query(Application)
        .filter(Application.user_id == current_user.id, Application.job_id == job_id)
        .first()
    )

    return {
        "id": job.id,
        "title": job.title,
        "company": job.company_name,
        "location": job.location,
        "type": job.type,
        "salary_range": job.salary_range,
        "description": job.description,
        "required_skills": (
            json.loads(job.required_skills)
            if (job.required_skills and job.required_skills.strip().startswith("["))
            else [s.strip() for s in job.required_skills.split(",")]
        )
        if job.required_skills
        else [],
        "interview_instructions": job.interview_instructions,
        "created_at": job.created_at.strftime("%Y-%m-%d") if job.created_at else None,
        "valid_through": job.valid_through.strftime("%Y-%m-%d")
        if job.valid_through
        else None,
        "already_applied": already_applied,
        "application_id": existing_app.id if existing_app else None,
        "application_status": existing_app.status if existing_app else None,
    }


@router.post("/jobs/{job_id}/apply")
def apply_to_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    body: ApplyRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    existing = (
        db.query(Application)
        .filter(Application.user_id == current_user.id, Application.job_id == job_id)
        .first()
    )
    if existing:
        return {"message": "Already applied", "application_id": existing.id}
    # Resolve which CV to attach. A cv_document_id in the request body selects
    # a specific CV document the candidate already owns (listed by
    # GET /candidate/cv-documents). Without it, fall back to the most recently
    # created application's CV text (existing behavior).
    latest_app = None
    cv_text = ""
    if body and body.cv_document_id:
        selected_doc = (
            db.query(CvDocument)
            .join(Application, Application.id == CvDocument.application_id)
            .filter(
                CvDocument.id == body.cv_document_id,
                Application.user_id == current_user.id,
            )
            .first()
        )
        if not selected_doc:
            raise HTTPException(status_code=404, detail="CV document not found")
        latest_app = (
            db.query(Application)
            .filter(Application.id == selected_doc.application_id)
            .first()
        )
        cv_text = (selected_doc.cv_text_anonymized or "") or (
            latest_app.cv_text_anonymized if latest_app else ""
        )
    else:
        latest_app = (
            db.query(Application)
            .filter(Application.user_id == current_user.id)
            .order_by(Application.created_at.desc())
            .first()
        )
        cv_text = latest_app.cv_text_anonymized if latest_app else ""
    _latest_er = (
        latest_app.evaluation_sessions[0].evaluation_result
        if latest_app
        and latest_app.evaluation_sessions
        and latest_app.evaluation_sessions[0].evaluation_result
        else None
    )
    if not cv_text or len(cv_text.strip()) < 50:
        # CV-builder candidates store their CV in CandidateProfile.builder_data
        # (no Application row is created until first apply). Synthesize CV text
        # from builder data so the apply gate is consistent with the CV review
        # path, which already falls back to builder_data.
        try:
            _builder = _load_builder_data(current_user, db)
            if _builder:
                _synth = _synthesize_cv_text(_builder)
                if _synth and len(_synth.strip()) >= 50:
                    cv_text = _synth.strip()
        except Exception as e:
            logger.warning(
                f"Failed to synthesize CV from builder_data for user {current_user.id}: {e}"
            )
    if not cv_text or len(cv_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="You must upload a CV and complete your profile analysis before applying.",
        )

    # Bug L-04 / U-02: previously the apply endpoint required only a
    # non-empty CV text. Candidates whose email was unverified, who
    # were missing a phone number, or who had not completed the
    # onboarding calibration could still apply, leaving recruiters
    # with half-empty records and a flood of "low quality" leads.
    # We now gate the apply on a small minimum profile:
    #   - email_verified (so recruiters can reply)
    #   - phone present (so recruiters can call/text)
    #   - full_name present (so the application isn't "null null")
    #   - CV analyzed with a non-failed verdict
    missing = []
    if not getattr(current_user, "email_verified", False):
        missing.append("verify your email")
    if not (get_user_phone(current_user) or "").strip():
        missing.append("add a phone number")
    if not (get_user_name(current_user) or "").strip():
        missing.append("add your full name")
    if (
        latest_app is None
        or ((_latest_er.final_score if _latest_er else None) is None)
        or latest_app.status in ("failed", "analysis_failed")
    ):
        # CV-builder candidates persist their analysis result (score/grade) in
        # CandidateProfile.builder_data, not in an Application row. Accept that
        # as a completed analysis so they are not blocked from applying.
        _builder_analyzed = False
        try:
            _bd = _load_builder_data(current_user, db)
            if _bd:
                _bd_score = _bd.get("score")
                _bd_grade = _bd.get("overall_grade")
                _bd_verdict = _bd.get("verdict")
                _builder_analyzed = (
                    (_bd_score is not None)
                    or bool(_bd_grade)
                    or (bool(_bd_verdict) and _bd_verdict != "failed")
                )
        except Exception as e:
            logger.warning(
                f"Failed to read builder_data analysis for user {current_user.id}: {e}"
            )
        if not _builder_analyzed:
            missing.append("complete your CV analysis")

    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                "Your profile isn't complete enough to apply. Please: "
                + ", ".join(missing)
                + "."
            ),
        )

    # The Application belongs to the company that posted the job (the
    # employer), NOT the candidate's own company membership. Candidates
    # applying to a public job are not members of the hiring company.
    company_id = getattr(job, "company_id", None)
    if not company_id:
        company_id = getattr(current_user, "_company_id", None)
    if not company_id:
        raise HTTPException(
            status_code=403, detail="Candidate company membership is required"
        )

    new_app = ApplicationService.create_application(
        db,
        company_id=company_id,
        application_type=ApplicationType.JOB,
        user_id=current_user.id,
        candidate_email=get_user_email(current_user),
        candidate_phone=get_user_phone(current_user),
        candidate_name=get_user_name(current_user),
        job_id=job_id,
        status="applied",
        declared_role=job.title,
        source=normalize_application_source(body.source if body else None),
        cv_text_anonymized=cv_text,
    )

    # Link application to the job's current rubric so the AI scoring pipeline
    # has rubric context for this application. Modern linkage lives on
    # Job.rubric_id; the legacy Rubric.job_id binding is a fallback.
    job_rubric = None
    if job.rubric_id:
        job_rubric = (
            db.query(Rubric)
            .filter(
                Rubric.id == job.rubric_id,
                Rubric.company_id == job.company_id,
                Rubric.is_active,
            )
            .first()
        )
    if job_rubric is None:
        job_rubric = (
            db.query(Rubric)
            .filter(
                Rubric.job_id == job_id,
                Rubric.company_id == job.company_id,
                Rubric.is_active,
            )
            .first()
        )
    if job_rubric:
        new_app.rubric_id = job_rubric.id
        logger.info(
            f"Linked application {new_app.id} to rubric {job_rubric.id} for job {job_id}"
        )

    db.commit()

    # Run job-specific CV analysis in the background (rubric-aware) so the
    # recruiter sees a job-specific CV score. The previous application's
    # analysis is NOT reused — only the CV text is carried over.
    from backend.routers.candidate.applications import run_cv_analysis
    from backend.trakin.core import safe_execute

    background_tasks.add_task(
        safe_execute,
        "candidate_apply_cv_analysis",
        run_cv_analysis,
        app_id=new_app.id,
        text=cv_text,
        role=job.title,
        db=db,
        job_id=job_id,
    )
    return {
        "message": "Application submitted successfully",
        "application_id": new_app.id,
    }


@router.get("/talent-graph")
def get_talent_graph(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    app = (
        db.query(Application)
        .filter(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
        .first()
    )
    if not app:
        return {
            "labels": ["Tech", "Soft", "Comm", "Problem Solving", "Experience"],
            "values": [],
            "has_data": False,
        }
    analysis = {}
    try:
        if app.analysis_json:
            analysis = json.loads(app.analysis_json)
    except Exception as e:
        logger.error(f"Error parsing analysis for talent graph: {e}")
    skill_metrics = analysis.get("skill_metrics") or analysis.get("skills")
    if skill_metrics and isinstance(skill_metrics, dict) and skill_metrics:
        # Bug B-4: only return real dimensions. Never pad with
        # fabricated "50" scores or invented keys.
        labels = list(skill_metrics.keys())[:5]
        values = [skill_metrics[label] for label in labels]
        return {"labels": labels, "values": values, "has_data": True}

    _er_tg = (
        app.evaluation_sessions[0].evaluation_result
        if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
        else None
    )
    score = _er_tg.final_score if _er_tg else None
    if score is None:
        return {
            "labels": ["Tech", "Soft", "Comm", "Problem Solving", "Experience"],
            "values": [],
            "has_data": False,
        }
    return {
        "labels": ["Overall Score"],
        "values": [score],
        "has_data": True,
    }


@router.get("/rubrics")
def list_candidate_rubrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company_id = getattr(current_user, "_company_id", None)
    if not company_id:
        last_app = (
            db.query(Application)
            .filter(
                Application.user_id == current_user.id,
                Application.company_id.isnot(None),
            )
            .order_by(Application.created_at.desc())
            .first()
        )
        if last_app:
            company_id = last_app.company_id
    if not company_id:
        return []

    rubrics = (
        db.query(Rubric)
        .filter(
            Rubric.company_id == company_id,
            Rubric.is_active == 1,
        )
        .order_by(Rubric.updated_at.desc())
        .all()
    )
    return [
        {
            "rubric_id": r.id,
            "title": r.title or "Untitled Rubric",
            "job_title": r.job.title if r.job else None,
            "description": r.description,
            "version": r.version,
            "seniority": r.complexity or "intermediate",
        }
        for r in rubrics
    ]
