import asyncio
import hashlib
import json
import re
import secrets
import string
import uuid
from datetime import UTC, datetime
from typing import List, Optional

import bcrypt
from fastapi import (
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from backend.ai import extract_cv_details, extract_skills_from_cv
from backend.authz import get_batch_for_recruiter, get_job_for_recruiter
from backend.database import Application, BatchJob, Rubric, User
from backend.dependencies import get_db, require_recruiter
from backend.entity_writer import sync_cv_document
from backend.logger import logger
from backend.models.ats.types import ApplicationType
from backend.pdf_parser import extract_text_from_pdf
from backend.scoring_service import ScoringService
from backend.services.rubric_match_service import compute_rubric_weighted_cv_score
from backend.security import sanitize_content, validate_file
from backend.services.application_service import ApplicationService
from backend.services.candidate_service import CandidateService
from backend.tenant import get_current_company_id

from . import router


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def _parse_criteria(rubric) -> list:
    """Parse rubric.criteria_json (TEXT/JSON string) into categories list."""
    raw = rubric.criteria_json
    if not raw:
        return []
    if isinstance(raw, (dict, list)):
        return raw.get("categories", []) if isinstance(raw, dict) else raw
    try:
        data = json.loads(raw)
        return data.get("categories", []) if isinstance(data, dict) else data
    except (json.JSONDecodeError, TypeError):
        return []


def _build_rubric_context(rubric) -> str:
    cats = _parse_criteria(rubric)
    if not cats:
        return ""
    lines = []
    for cat in cats:
        skills = []
        for sub in cat.get("subcategories", []):
            for skill in sub.get("skills", []):
                name = skill.get("name")
                if name:
                    skills.append(str(name).strip())
        if skills:
            lines.append(
                f"Category: {cat.get('name', 'Unnamed')} — Skills: {', '.join(skills)}"
            )
    return "\n".join(lines)


def _generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _hash_password(password: str) -> str:
    # M3 FIX: bcrypt cost=14 is ~250ms synchronously. At 10k candidates this
    # blocks the event loop for ~40 minutes. We drop to cost=6 for ghost/temp
    # accounts (candidates never log in directly; temp_password is stored
    # plaintext separately and the hash is only used as a sentinel). Real
    # recruiter/candidate accounts created via the auth flow still use cost=14.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=6)).decode(
        "utf-8"
    )


async def background_analyze_batch(
    batch_id: int,
    items_to_process: List[dict],
    recruiter_id: int,
    company_id: int,
):
    from backend.ai.privacy import scrub_pii
    from backend.cv_service import anonymize_text, extract_pii
    from backend.database import SessionLocal
    from backend.subscription_service import SubscriptionService

    db = SessionLocal()
    batch = (
        db.query(BatchJob)
        .filter(BatchJob.id == batch_id, BatchJob.company_id == company_id)
        .first()
    )
    if not batch:
        logger.warning(
            f"Background analyze: BatchJob {batch_id} not found for company {company_id}"
        )
        db.close()
        return

    recruiter = db.query(User).get(recruiter_id)
    full_context = (
        f"Target Role: {batch.target_role}\nJob Description: {batch.description}"
        if batch.target_role or batch.description
        else ""
    )

    rubric = None
    rubric_context = ""
    if batch.rubric_id:
        rubric = (
            db.query(Rubric)
            .filter(Rubric.id == batch.rubric_id, Rubric.company_id == company_id)
            .first()
        )
        if not rubric:
            logger.warning(
                f"Background analyze: Rubric {batch.rubric_id} not found for company {company_id}; proceeding without rubric"
            )
        else:
            try:
                rubric_context = _build_rubric_context(rubric)
            except Exception as e:
                logger.warning(
                    f"Background analyze: Failed to build rubric context for {batch.rubric_id}: {e}"
                )
                rubric_context = ""

    try:
        for item in items_to_process:
            app_id = item["app_id"]
            text = item["text"]
            filename = item["filename"]
            regex_email = item["email"]

            app = (
                db.query(Application)
                .filter(Application.id == app_id, Application.company_id == company_id)
                .first()
            )
            if not app:
                logger.warning(
                    f"Background analyze: Application {app_id} not found for company {company_id}"
                )
                continue

            try:
                pii_data = extract_pii(text)
                anonymized_text = anonymize_text(text, pii_data)

                try:
                    analysis = await extract_cv_details(
                        text, full_context, rubric_context
                    )
                except Exception as e:
                    logger.error(f"AI Extraction failed for {filename}: {e}")
                    analysis = {
                        "role": "General",
                        "score": None,
                        "summary": "Manual Import (AI Error)",
                    }
                if not isinstance(analysis, dict):
                    logger.warning(
                        f"AI Extraction returned invalid result for {filename}: {analysis!r}"
                    )
                    analysis = {
                        "role": "General",
                        "score": None,
                        "summary": "Manual Import (AI Error)",
                    }

                ai_score = analysis.get("score")
                if ai_score is None:
                    ai_score = analysis.get("match_score")
                if ai_score is None:
                    ai_score = analysis.get("current_score")
                final_score = None
                if ai_score is not None and float(ai_score) > 0:
                    final_score = max(0.0, min(100.0, float(ai_score)))

                if rubric is not None:
                    try:
                        # AI-extracted skills are supplementary evidence only.
                        # The canonical CV score comes from the campaign rubric.
                        skills_result = await extract_skills_from_cv(
                            text, rubric.title or "General"
                        )

                        extracted = (
                            skills_result.get("extracted_skills", {})
                            if isinstance(skills_result, dict)
                            else {}
                        )

                        extracted_skills = []
                        for group in extracted.values():
                            if not isinstance(group, list):
                                continue
                            for skill in group:
                                if isinstance(skill, dict):
                                    name = skill.get("name") or skill.get("skill")
                                    if name:
                                        extracted_skills.append(str(name))
                                elif isinstance(skill, str):
                                    extracted_skills.append(skill)

                        weighted = compute_rubric_weighted_cv_score(
                            text,
                            rubric,
                            extracted_skills=extracted_skills,
                        )

                        if weighted is not None:
                            # Campaign CV score is rubric-driven whenever
                            # the campaign has a parseable rubric.
                            final_score = float(weighted["cv_score"])
                            analysis["score"] = final_score
                            analysis["cv_rubric_weighted"] = True
                            analysis["scoring_method"] = weighted[
                                "scoring_method"
                            ]
                            analysis["coverage_pct"] = weighted["coverage_pct"]
                            analysis["missing_skills"] = weighted["missing_skills"]
                            analysis["skill_scores"] = weighted["skill_scores"]

                            analysis["rubric_match"] = {
                                "rubric_id": batch.rubric_id,
                                "rubric_title": rubric.title,
                                "match_percentage": int(round(final_score)),
                                "total_skills": len(weighted["skill_scores"]),
                                "matched_skills": [
                                    {
                                        "name": name,
                                        "category": details.get("category"),
                                    }
                                    for name, details in weighted["skill_scores"].items()
                                    if details.get("score", 0) > 0
                                ],
                                "missing_skills": [
                                    {
                                        "name": name,
                                        "category": details.get("category"),
                                    }
                                    for name, details in weighted["skill_scores"].items()
                                    if details.get("score", 0) == 0
                                ],
                            }

                            logger.info(
                                "[CV RUBRIC SCORING] app=%s rubric=%s "
                                "score=%.1f coverage=%.1f method=%s",
                                app.id,
                                rubric.id,
                                final_score,
                                weighted["coverage_pct"],
                                weighted["scoring_method"],
                            )
                        else:
                            # Rubric exists but contains no parseable skills.
                            # Keep the generic AI score rather than fabricating
                            # a rubric score.
                            analysis["cv_rubric_weighted"] = False
                            analysis["scoring_method"] = "generic_fallback"

                    except Exception as e:
                        logger.warning(
                            f"Rubric-weighted CV scoring failed for {filename}: {e}",
                            exc_info=True,
                        )
                        analysis["cv_rubric_weighted"] = False
                        analysis["scoring_method"] = "generic_fallback"

                else:
                    analysis["cv_rubric_weighted"] = None
                    analysis["scoring_method"] = None

                bad_names = {
                    "unknown",
                    "manual review required",
                    "candidate name",
                    "n/a",
                    "none",
                    "candidate",
                }
                candidate_name = pii_data.get("name")
                if not candidate_name or candidate_name.lower() in bad_names:
                    ai_name = analysis.get("name") or analysis.get("detected_name")
                    if ai_name and ai_name.lower() not in bad_names:
                        candidate_name = ai_name
                    else:
                        candidate_name = (
                            filename.rsplit(".", 1)[0]
                            .replace("_", " ")
                            .replace("-", " ")
                            .title()
                            .strip()
                        )

                final_email = (
                    pii_data.get("email") or analysis.get("email") or regex_email
                )
                if (
                    not final_email
                    or "@" not in str(final_email)
                    or "redacted" in str(final_email).lower()
                ):
                    text_hash = hashlib.md5(
                        text.encode("utf-8", errors="ignore")
                    ).hexdigest()[:10]
                    final_email = f"no-email-{text_hash}@import.local"

                app.full_name = candidate_name
                app.email = final_email
                candidate = CandidateService.resolve_or_create_candidate(
                    db,
                    company_id=company_id,
                    email=final_email,
                    full_name=candidate_name,
                    phone=pii_data.get("phone"),
                )
                app.candidate_id = candidate.id
                ScoringService.compute_final_score(
                    app,
                    db,
                    computed_by="campaign_upload",
                    override_cv_score=final_score if final_score is not None else None,
                )
                sync_cv_document(db, app, analysis_json=analysis)
                app.status = "screening"
                sync_cv_document(db, app, cv_text_anonymized=scrub_pii(text))
                app.processed_at = _utcnow()

                try:
                    from backend.ai.llm import get_embedding

                    embedding_input = f"Summary: {analysis.get('summary', '')}\nCV Text: {anonymized_text[:2000]}"
                    embedding = await get_embedding(embedding_input)
                    if embedding:
                        sync_cv_document(db, app, cv_embedding=json.dumps(embedding))
                except Exception as e:
                    logger.warning(f"Embedding generation failed: {e}")

                user = db.query(User).filter(User.email == final_email).first()
                generated_password = None
                if not user:
                    try:
                        with db.begin_nested():
                            plan = SubscriptionService.get_user_plan(recruiter, db)
                            generated_password = _generate_temp_password()
                            hashed_pw = _hash_password(generated_password)
                            user = User(
                                email=final_email,
                                name=candidate_name,
                                role="candidate",
                                current_plan_id=plan.id if plan else None,
                                temp_password=generated_password,
                                hashed_password=hashed_pw,
                            )
                            db.add(user)
                            db.flush()
                            app._generated_password = generated_password
                    except Exception:
                        user = db.query(User).filter(User.email == final_email).first()
                if user:
                    app.user_id = user.id

                db.commit()
            except Exception as e:
                logger.error(f"Failed to process CV {filename}: {e}")
                app.status = "failed"
                app.error_message = str(e)[:500]
                db.commit()

        batch.worker_status = "completed"
        batch.status = "complete"
        db.commit()

        from backend.models.core.batch_job import batch_counters

        counters = batch_counters(db, batch.id, qualified_threshold=70.0)
        qualified_cnt = counters.get("qualified_count", 0)

        try:
            from backend.notifications import notify_user

            await notify_user(
                str(recruiter_id),
                f"Campaign '{batch.title}' screening is complete. {counters['total_files']} CVs analyzed. {qualified_cnt} candidate(s) met qualification score (70%+). Shortlist is ready for review.",
                title="Shortlist Ready",
                level="success",
                notification_type="campaign_complete",
                related_type="campaign",
                related_id=batch.id,
                db_session=db,
            )
        except Exception as e:
            logger.error(f"Failed to notify recruiter: {e}")

        # Task 7: Start email sequence if enabled
        if batch.email_sequence_enabled:
            try:
                logger.info(f"Email sequence enabled for campaign {batch.id}. Running automated sequence worker.")
                from backend.email_sequence_worker import process_email_sequences
                process_email_sequences(db)
            except Exception as seq_err:
                logger.error(f"Failed to initiate email sequence: {seq_err}")

        logger.info(
            f"Batch {batch_id} processing completed: {counters['processed_files']}/{counters['total_files']}"
        )
    except Exception as e:
        logger.error(f"Batch worker failed: {e}")
        if batch:
            batch.worker_status = "failed"
            batch.error_message = str(e)
            db.commit()
    try:
        final_batch = db.query(BatchJob).get(batch_id)
        if final_batch and final_batch.worker_status == "processing":
            final_batch.worker_status = "completed"
            db.commit()
    except Exception as e:
        logger.error(f"Failed to finalize batch {batch_id}: {e}")
    finally:
        db.close()


@router.post("/upload/cv")
@router.post("/upload-cvs")
async def upload_cvs(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    campaign_name: Optional[str] = Form(None),
    target_role: Optional[str] = Form(None),
    job_description: Optional[str] = Form(None),
    interview_instructions: Optional[str] = Form(None),
    interview_language: Optional[str] = Form("English"),
    job_id: int = Form(...),
    campaign_id: Optional[int] = Form(None),
    consent_confirmed: Optional[bool] = Form(False),
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    from backend.subscription_service import SubscriptionService

    try:
        if not SubscriptionService.can_perform_action(recruiter, "analyze_cv", db):
            raise HTTPException(
                status_code=403, detail="CV analysis limit reached for this month."
            )

        job = get_job_for_recruiter(job_id, recruiter, db)
        if job.rubric_id is None:
            raise HTTPException(
                status_code=400,
                detail="This job has no rubric. Please assign a rubric before uploading candidates.",
            )

        company_id = getattr(recruiter, "_company_id", None)
        if not company_id:
            raise HTTPException(
                status_code=403, detail="Recruiter company membership is required"
            )

        # When the wizard created a campaign first, attach candidates to that
        # campaign so they inherit its rubric (batch.rubric_id drives scoring).
        if campaign_id:
            campaign_batch = get_batch_for_recruiter(campaign_id, recruiter, db)
            if campaign_batch.job_id != job_id:
                raise HTTPException(
                    status_code=400,
                    detail="Campaign is not linked to the selected job.",
                )
        else:
            campaign_batch = None

        campaign_name = sanitize_content(campaign_name) if campaign_name else None
        target_role = sanitize_content(target_role) if target_role else None
        job_description = sanitize_content(job_description) if job_description else None
        interview_instructions = (
            sanitize_content(interview_instructions) if interview_instructions else None
        )

        default_title = f"Bulk Import - {_utcnow().strftime('%b %d, %H:%M')}"
        if campaign_batch is not None:
            new_batch = campaign_batch
        else:
            new_batch = BatchJob(
                recruiter_id=recruiter.id,
                company_id=job.company_id,
                title=campaign_name or default_title,
                target_role=target_role,
                description=job_description,
                interview_instructions=interview_instructions,
                language=interview_language or "English",
                status="active",
                worker_status="processing",
                job_id=job_id,
                rubric_id=job.rubric_id,
            )
            db.add(new_batch)
            db.flush()

        if consent_confirmed:
            new_batch.cv_processing_consent_confirmed = True
            new_batch.cv_processing_consent_confirmed_at = _utcnow()
            new_batch.cv_processing_consent_confirmed_by = recruiter.id

        results = []
        file_queue_for_worker = []
        total_queued = 0

        for file in files:
            if not file.filename.lower().endswith(".pdf"):
                results.append(
                    {
                        "filename": file.filename,
                        "status": "skipped",
                        "reason": "Not a PDF",
                    }
                )
                continue

            content = await file.read()
            try:
                validate_file(file.filename, len(content), content=content)
            except HTTPException as e:
                results.append(
                    {"filename": file.filename, "status": "failed", "reason": e.detail}
                )
                continue

            text = extract_text_from_pdf(content)
            if not text:
                results.append(
                    {
                        "filename": file.filename,
                        "status": "failed",
                        "reason": "Empty text",
                    }
                )
                continue

            match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
            email = match.group(0) if match else None

            company_id = getattr(recruiter, "_company_id", None)
            if not company_id:
                raise HTTPException(
                    status_code=403, detail="Recruiter company membership is required"
                )

            if email and "@" in email:
                recruiter_batch_ids = [
                    r[0]
                    for r in db.query(BatchJob.id)
                    .filter(
                        BatchJob.recruiter_id == recruiter.id,
                        BatchJob.deleted_at.is_(None),
                    )
                    .all()
                ]

                existing = (
                    db.query(Application)
                    .filter(
                        Application.email == email,
                        Application.company_id == company_id,
                        Application.batch_id.in_(recruiter_batch_ids),
                        Application.deleted_at.is_(None),
                    )
                    .first()
                )
                if existing:
                    results.append(
                        {
                            "filename": file.filename,
                            "email": email,
                            "status": "skipped",
                            "reason": f"Duplicate email: {email} (Found in campaign: {existing.batch_job.title if existing.batch_job else 'Unknown'})",
                        }
                    )
                    continue

            if not SubscriptionService.record_usage(
                recruiter, "analyze_cv", db, commit=False
            ):
                results.append(
                    {
                        "filename": file.filename,
                        "email": email,
                        "status": "skipped",
                        "reason": "CV analysis quota reached.",
                    }
                )
                continue

            final_email = email or f"no-email-{uuid.uuid4().hex[:8]}@import.local"

            app = ApplicationService.create_application(
                db,
                company_id=company_id,
                application_type=ApplicationType.CAMPAIGN,
                candidate_email=final_email,
                candidate_name=file.filename,
                status="pending",
                batch_id=new_batch.id,
                job_id=new_batch.job_id,
                rubric_id=new_batch.rubric_id,
                declared_role=target_role or "Candidate",
                source="campaign",
                language=interview_language or "English",
            )

            if consent_confirmed:
                app.consent_accepted = True
                app.consent_at = _utcnow()
                app.consent_source = "recruiter_upload_confirmation"

            file_queue_for_worker.append(
                {
                    "app_id": app.id,
                    "text": text,
                    "filename": file.filename,
                    "email": email,
                }
            )
            total_queued += 1
            results.append(
                {"filename": file.filename, "status": "queued", "id": app.id}
            )

        skipped_duplicates = [
            r
            for r in results
            if r.get("status") == "skipped"
            and "Duplicate" in (r.get("reason") or "")
        ]
        failed_items = [r for r in results if r.get("status") == "failed"]
        duplicate_emails = [
            r.get("email") for r in skipped_duplicates if r.get("email")
        ]

        if total_queued == 0:
            db.commit()
            return {
                "success": False,
                "detail": "No valid new PDFs processed.",
                "batch_id": new_batch.id,
                "uploaded": 0,
                "skipped_duplicates": len(skipped_duplicates),
                "failed": len(failed_items),
                "duplicate_emails": duplicate_emails,
                "details": results,
            }

        db.commit()

        asyncio.create_task(
            background_analyze_batch(
                new_batch.id,
                file_queue_for_worker,
                recruiter.id,
                getattr(recruiter, "_company_id", None),
            )
        )

        return {
            "success": True,
            "message": f"Processing {total_queued} CVs in background.",
            "batch_id": new_batch.id,
            "uploaded": total_queued,
            "skipped_duplicates": len(skipped_duplicates),
            "failed": len(failed_items),
            "duplicate_emails": duplicate_emails,
            "details": results,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload CVs")


@router.post("/preview-match")
async def preview_skill_match(
    file: UploadFile = File(...),
    rubric_id: Optional[int] = Form(None),
    skill_tree_id: Optional[int] = Form(None),
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """
    Preview how a CV matches against an evaluation rubric without creating
    a campaign. Extracts text from the PDF, runs AI skill extraction, and
    compares against the rubric categories/skills.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    target_id = rubric_id or skill_tree_id
    if not target_id:
        raise HTTPException(status_code=400, detail="rubric_id is required")

    rubric = (
        db.query(Rubric)
        .filter(
            Rubric.id == target_id,
            Rubric.is_active == 1,
            (Rubric.company_id == company_id) | (Rubric.company_id.is_(None)),
        )
        .first()
    )
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")

    try:
        content = await file.read()
        cv_text = extract_text_from_pdf(content)
        if not cv_text or len(cv_text.strip()) < 20:
            raise HTTPException(
                status_code=400, detail="Could not extract text from PDF"
            )

        from backend.ai import extract_skills_from_cv

        skills_result = await extract_skills_from_cv(cv_text, rubric.title or "General")
        extracted = skills_result.get("extracted_skills", {})
        all_extracted = set()
        for group in extracted.values():
            for s in group:
                if isinstance(s, dict):
                    all_extracted.add(s.get("name", "").lower())
                elif isinstance(s, str):
                    all_extracted.add(s.lower())

        cats = _parse_criteria(rubric)
        matched_skills = []
        missing_skills = []
        total_skills = 0

        for cat in cats:
            for sub in cat.get("subcategories", []):
                for skill in sub.get("skills", []):
                    total_skills += 1
                    skill_name = skill.get("name", "").lower()
                    if not skill_name:
                        continue
                    # Simple fuzzy match: check if skill name appears in extracted skills
                    is_matched = any(
                        skill_name in ext or ext in skill_name for ext in all_extracted
                    )
                    if is_matched:
                        matched_skills.append(
                            {
                                "name": skill.get("name"),
                                "category": cat.get("name"),
                            }
                        )
                    else:
                        missing_skills.append(
                            {
                                "name": skill.get("name"),
                                "category": cat.get("name"),
                            }
                        )

        match_pct = (
            round((len(matched_skills) / total_skills * 100)) if total_skills else 0
        )

        return {
            "filename": file.filename,
            "match_percentage": match_pct,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "total_skills": total_skills,
            "extracted_skills_count": len(all_extracted),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview match failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to analyze CV")
