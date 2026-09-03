import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, selectinload

from backend.ai.llm import call_groq_cascade
from backend.database import (
    Application,
    Job,
    ReEngagementCampaign,
    ReEngagementCandidate,
)
from backend.logger import logger

RE_ENGAGEMENT_COOLDOWN_DAYS = 90
DEFAULT_MIN_SCORE = 65
DAILY_SENDING_LIMIT = 50


class ReEngagementEngine:
    @staticmethod
    async def find_matching_candidates(
        job: Job,
        recruiter_id: int,
        db: Session,
        min_score: float = DEFAULT_MIN_SCORE,
        limit: int = 20,
    ) -> list:
        candidates = []
        past_apps = (
            db.query(Application)
            .options(selectinload(Application.evaluation_sessions))
            .filter(
                Application.job_id == job.id,
                Application.status.in_(["rejected", "withdrawn"]),
                Application.deleted_at.is_(None),
            )
            .limit(200)
            .all()
        )
        if not past_apps:
            return []

        for app in past_apps:
            candidate_data = ReEngagementEngine.get_candidate_from_application(app)
            if not candidate_data:
                continue
            if not ReEngagementEngine.check_reengagement_limits(
                app.user_id or 0, recruiter_id, db
            ):
                continue
            try:
                result = await ReEngagementEngine.compute_candidate_job_match(
                    candidate_data, job
                )
            except Exception as e:
                logger.error(f"Match computation failed for app {app.id}: {e}")
                result = await ReEngagementEngine._rule_based_fallback(
                    candidate_data, job
                )
            if result.get("match_score", 0) >= min_score:
                candidates.append(
                    {
                        "application_id": app.id,
                        "candidate_id": app.user_id,
                        "candidate_name": app.full_name,
                        "candidate_email": app.email,
                        "declared_role": app.declared_role,
                        "original_status": app.status,
                        "original_date": app.created_at,
                        "match_score": result["match_score"],
                        "match_reason": result.get("match_reason", ""),
                        "scoring_breakdown": result.get("scoring_breakdown", {}),
                    }
                )

        candidates.sort(key=lambda x: x["match_score"], reverse=True)
        return candidates[:limit]

    @staticmethod
    async def compute_candidate_job_match(candidate_data: dict, job: Job) -> dict:
        prompt = f"""You are a recruitment matching AI. Analyze how well this past candidate matches the job.

Job Title: {job.title}
Job Skills: {job.required_skills or "Not specified"}
Job Description: {(job.description or "")[:1500]}

Candidate Declared Role: {candidate_data.get("declared_role", "Unknown")}
Candidate Detected Role: {candidate_data.get("detected_role", "Unknown")}
Candidate Skills: {candidate_data.get("skills", "None listed")}
Candidate CV Score: {candidate_data.get("cv_score", "N/A")}
Candidate Overall Score: {candidate_data.get("overall_score", "N/A")}

Return JSON with:
- "match_score": int 0-100 overall match
- "match_reason": string explanation
- "scoring_breakdown": {{"role_similarity": int, "skills_overlap": int, "quality_score": int}}"""
        try:
            data = await call_groq_cascade(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1024,
                json_mode=True,
            )
            if isinstance(data, dict) and "match_score" in data:
                return data
        except Exception:
            pass
        return await ReEngagementEngine._rule_based_fallback(candidate_data, job)

    @staticmethod
    async def _rule_based_fallback(candidate_data: dict, job: Job) -> dict:
        score = 50
        reasons = []
        cd_role = (candidate_data.get("declared_role") or "").lower()
        ct_role = (candidate_data.get("detected_role") or "").lower()
        jt = (job.title or "").lower()
        jt_words = set(jt.split())
        role_words = set(cd_role.split()) | set(ct_role.split())
        common = jt_words & role_words
        role_sim = min(len(common) * 15, 40)
        if role_sim > 0:
            reasons.append(f"Role overlap: {len(common)} matching keywords")

        candidate_skills = set(
            (candidate_data.get("skills") or "").lower().replace(",", " ").split()
        )
        job_skills = set((job.required_skills or "").lower().replace(",", " ").split())
        if job_skills and candidate_skills:
            overlap = candidate_skills & job_skills
            if len(job_skills) > 0:
                skills_pct = len(overlap) / len(job_skills)
                skills_score = int(skills_pct * 30)
                if skills_score > 0:
                    reasons.append(
                        f"Skills overlap: {len(overlap)}/{len(job_skills)} matched"
                    )
        else:
            skills_score = 0

        cv = candidate_data.get("cv_score") or 0
        ov = candidate_data.get("overall_score") or 0
        quality = int((cv * 0.5 + ov * 0.5) * 0.05)
        score = role_sim + skills_score + quality
        if not reasons:
            reasons.append("Rule-based fallback match")
        return {
            "match_score": min(score, 100),
            "match_reason": "; ".join(reasons),
            "scoring_breakdown": {
                "role_similarity": role_sim,
                "skills_overlap": skills_score,
                "quality_score": quality,
            },
        }

    @staticmethod
    def get_candidate_from_application(app: Application) -> dict:
        if not app:
            return None
        skills = None
        if app.analysis_json:
            try:
                aj = (
                    json.loads(app.analysis_json)
                    if isinstance(app.analysis_json, str)
                    else app.analysis_json
                )
                skills = aj.get("skills", app.declared_role)
            except (json.JSONDecodeError, TypeError):
                skills = app.declared_role
        _er = (
            app.evaluation_sessions[0].evaluation_result
            if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
            else None
        )
        return {
            "declared_role": app.declared_role,
            "detected_role": app.detected_role,
            "skills": skills,
            "cv_score": (_er.cv_score if _er else None) or 0,
            "overall_score": (_er.final_score if _er else None) or 0,
            "created_at": app.created_at,
        }

    @staticmethod
    def check_reengagement_limits(
        candidate_id: int, recruiter_id: int, db: Session
    ) -> bool:
        if candidate_id <= 0:
            return True
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            days=RE_ENGAGEMENT_COOLDOWN_DAYS
        )
        recent = (
            db.query(ReEngagementCandidate)
            .join(ReEngagementCampaign)
            .filter(
                ReEngagementCampaign.recruiter_id == recruiter_id,
                ReEngagementCandidate.application_id == candidate_id,
                ReEngagementCandidate.invited_at.isnot(None),
                ReEngagementCandidate.invited_at >= cutoff,
            )
            .first()
        )
        return recent is None

    @staticmethod
    def check_daily_sending_limit(recruiter_id: int, db: Session) -> int:
        today_start = (
            datetime.now(UTC).replace(tzinfo=None).replace(hour=0, minute=0, second=0)
        )
        sent_today = (
            db.query(ReEngagementCandidate)
            .join(ReEngagementCampaign)
            .filter(
                ReEngagementCampaign.recruiter_id == recruiter_id,
                ReEngagementCandidate.invited_at.isnot(None),
                ReEngagementCandidate.invited_at >= today_start,
            )
            .count()
        )
        return max(0, DAILY_SENDING_LIMIT - sent_today)

    @staticmethod
    async def create_campaign(
        job: Job, recruiter_id: int, db: Session
    ) -> ReEngagementCampaign:
        campaign = ReEngagementCampaign(
            recruiter_id=recruiter_id,
            job_id=job.id,
            status="analyzing",
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)

        try:
            matches = await ReEngagementEngine.find_matching_candidates(
                job, recruiter_id, db
            )
            campaign.total_candidates = len(matches)
            campaign.matched_candidates = len(
                [m for m in matches if m["match_score"] >= DEFAULT_MIN_SCORE]
            )
            if matches:
                campaign.avg_match_score = sum(m["match_score"] for m in matches) / len(
                    matches
                )

            for m in matches:
                rec = ReEngagementCandidate(
                    campaign_id=campaign.id,
                    application_id=m["application_id"],
                    match_score=m["match_score"],
                    match_reason=json.dumps(
                        {
                            "reason": m["match_reason"],
                            "breakdown": m.get("scoring_breakdown", {}),
                        }
                    ),
                )
                db.add(rec)
            campaign.status = "ready"
        except Exception as e:
            logger.error(f"Campaign analysis failed: {e}")
            campaign.status = "completed"
            campaign.completed_at = datetime.now(UTC).replace(tzinfo=None)

        db.commit()
        db.refresh(campaign)
        return campaign
