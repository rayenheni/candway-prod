import asyncio
import json
from datetime import UTC, datetime
from typing import Optional

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.ai.llm import call_groq_cascade
from backend.config import get_settings
from backend.database import Application, Job, SourcedCandidate, User
from backend.logger import logger
from backend.profile_helpers import (
    get_user_bio,
    get_user_headline,
    get_user_name,
    get_user_skills,
)


class SourcingAgent:
    @staticmethod
    async def source_for_job(
        job_id: int,
        recruiter_id: int,
        db: Session,
        sources: Optional[list] = None,
        max_candidates: int = 20,
    ) -> dict:
        if sources is None:
            sources = ["github", "stackoverflow", "internal"]

        settings = get_settings()
        today_start = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        daily_count = (
            db.query(func.count(SourcedCandidate.id))
            .filter(
                SourcedCandidate.recruiter_id == recruiter_id,
                SourcedCandidate.created_at >= today_start,
            )
            .scalar()
        )
        if daily_count >= settings.sourcing_daily_limit:
            return {
                "status": "rate_limited",
                "detail": f"Daily sourcing limit ({settings.sourcing_daily_limit}) reached",
                "sourced_count": 0,
            }

        job = (
            db.query(Job)
            .filter(Job.id == job_id, Job.recruiter_id == recruiter_id)
            .first()
        )
        if not job:
            return {"status": "error", "detail": "Job not found", "sourced_count": 0}

        keywords = await SourcingAgent.extract_search_keywords(job)
        max_per_source = max(1, max_candidates // len(sources))
        all_candidates = []
        source_tasks = []

        for source in sources:
            if source == "github":
                source_tasks.append(
                    SourcingAgent.search_github(keywords, max_per_source)
                )
            elif source == "stackoverflow":
                source_tasks.append(
                    SourcingAgent.search_stackoverflow(keywords, max_per_source)
                )
            elif source == "internal":
                source_tasks.append(
                    asyncio.to_thread(
                        SourcingAgent.search_internal,
                        db,
                        keywords,
                        recruiter_id,
                        max_per_source,
                    )
                )

        results = await asyncio.gather(*source_tasks, return_exceptions=True)

        for source_name, result in zip(sources, results):
            if isinstance(result, Exception):
                logger.error(f"Sourcing source {source_name} failed: {result}")
                continue
            for candidate in result:
                candidate["_source"] = source_name
            all_candidates.extend(result)

        scored = []
        for candidate in all_candidates[:max_candidates]:
            try:
                score_result = await SourcingAgent.score_candidate(candidate, job)
                candidate["match_score"] = score_result.get("score", 0)
                candidate["match_data"] = json.dumps(score_result)
                scored.append(candidate)
            except Exception as e:
                logger.error(
                    f"Scoring failed for candidate {candidate.get('name', 'unknown')}: {e}"
                )

        scored.sort(key=lambda c: c.get("match_score", 0), reverse=True)

        saved_count = 0
        for c in scored:
            existing = (
                db.query(SourcedCandidate)
                .filter(
                    SourcedCandidate.recruiter_id == recruiter_id,
                    SourcedCandidate.job_id == job_id,
                    SourcedCandidate.source == c.get("_source"),
                    SourcedCandidate.source_id == c.get("source_id", ""),
                )
                .first()
            )
            if existing:
                continue

            sc = SourcedCandidate(
                recruiter_id=recruiter_id,
                job_id=job_id,
                source=c.get("_source"),
                source_id=c.get("source_id", ""),
                name=c.get("name", "Unknown"),
                headline=c.get("headline", ""),
                location=c.get("location", ""),
                profile_url=c.get("profile_url", ""),
                avatar_url=c.get("avatar_url", ""),
                skills=c.get("skills", ""),
                bio=c.get("bio", ""),
                match_score=c.get("match_score", 0),
                match_data=c.get("match_data", "{}"),
            )
            db.add(sc)
            saved_count += 1

        db.commit()

        return {
            "status": "completed",
            "sourced_count": saved_count,
            "total_found": len(scored),
            "sources_used": sources,
        }

    @staticmethod
    async def extract_search_keywords(job: Job) -> dict:
        prompt = f"""
You are a recruiter AI. Extract search keywords from the job below.
Return JSON with keys: roles (array), skills (array), locations (array), seniority (string), keywords (array).

Job Title: {job.title}
Required Skills: {job.required_skills}
Location: {job.location}
Description: {job.description[:2000]}
"""
        try:
            result = await call_groq_cascade(
                [{"role": "user", "content": prompt}], json_mode=True
            )
            if isinstance(result, dict):
                return result
            return json.loads(result) if isinstance(result, str) else {}
        except Exception as e:
            logger.error(f"Keyword extraction failed: {e}")
            return {
                "roles": [job.title],
                "skills": [
                    s.strip()
                    for s in (job.required_skills or "").split(",")
                    if s.strip()
                ],
                "locations": [job.location] if job.location else [],
                "seniority": "mid",
                "keywords": [job.title],
            }

    @staticmethod
    async def search_github(keywords: dict, max_per_source: int) -> list:
        settings = get_settings()
        headers = {"Accept": "application/vnd.github.v3+json"}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"

        candidates = []
        search_terms = keywords.get("keywords", []) + keywords.get("skills", [])
        search_query = " ".join(search_terms[:5])

        if keywords.get("locations"):
            location = keywords["locations"][0]
            search_query += f" location:{location}"

        params = {
            "q": search_query,
            "per_page": min(max_per_source, 30),
            "sort": "repositories",
            "order": "desc",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(
                    "https://api.github.com/search/users",
                    headers=headers,
                    params=params,
                )
                if resp.status_code not in (200, 403):
                    logger.warning(f"GitHub search failed: {resp.status_code}")
                    return []

                if resp.status_code == 403:
                    logger.warning(
                        "GitHub rate limit hit, continuing without GitHub results"
                    )
                    return []

                data = resp.json()
                for item in data.get("items", [])[:max_per_source]:
                    user_resp = await client.get(
                        item["url"], headers=headers, timeout=15
                    )
                    if user_resp.status_code != 200:
                        continue
                    user_data = user_resp.json()

                    repos_resp = await client.get(
                        f"https://api.github.com/users/{item['login']}/repos",
                        headers=headers,
                        params={"sort": "updated", "per_page": 5},
                        timeout=15,
                    )
                    repo_topics = []
                    if repos_resp.status_code == 200:
                        for repo in repos_resp.json():
                            repo_topics.extend(repo.get("topics", []))

                    all_skills = list(
                        set((user_data.get("bio") or "").split() + repo_topics)
                    )

                    candidates.append(
                        {
                            "source_id": str(item["id"]),
                            "name": user_data.get("name") or item["login"],
                            "headline": user_data.get("bio")
                            or f"GitHub user: {item['login']}",
                            "location": user_data.get("location") or "",
                            "profile_url": item["html_url"],
                            "avatar_url": item.get("avatar_url", ""),
                            "skills": ", ".join(all_skills[:20]),
                            "bio": user_data.get("bio") or "",
                        }
                    )
            except Exception as e:
                logger.error(f"GitHub search error: {e}")

        return candidates

    @staticmethod
    async def search_stackoverflow(keywords: dict, max_per_source: int) -> list:
        settings = get_settings()
        headers = {}
        if settings.stackoverflow_token:
            headers["Authorization"] = f"Bearer {settings.stackoverflow_token}"

        candidates = []
        tags = keywords.get("skills", [])[:5]
        tag_query = (
            ";".join(tags) if tags else ";".join(keywords.get("keywords", [])[:5])
        )
        if not tag_query:
            return []

        params = {
            "order": "desc",
            "sort": "reputation",
            "site": "stackoverflow",
            "pagesize": min(max_per_source, 20),
            "filter": "withbody",
        }
        if tag_query:
            params["tagged"] = tag_query

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(
                    "https://api.stackexchange.com/2.3/users",
                    headers=headers,
                    params=params,
                )
                if resp.status_code != 200:
                    logger.warning(f"StackOverflow search failed: {resp.status_code}")
                    return []

                data = resp.json()
                for item in data.get("items", [])[:max_per_source]:
                    badges = []
                    badge_count = item.get("badge_counts", {})
                    if badge_count.get("gold"):
                        badges.append(f"Gold:{badge_count['gold']}")
                    if badge_count.get("silver"):
                        badges.append(f"Silver:{badge_count['silver']}")
                    if badge_count.get("bronze"):
                        badges.append(f"Bronze:{badge_count['bronze']}")

                    candidates.append(
                        {
                            "source_id": str(item["user_id"]),
                            "name": item.get("display_name", "Unknown"),
                            "headline": f"Reputation: {item.get('reputation', 0)} | Badges: {', '.join(badges)}",
                            "location": item.get("location") or "",
                            "profile_url": item.get("link", ""),
                            "avatar_url": item.get("profile_image", ""),
                            "skills": tag_query,
                            "bio": item.get("about_me", "")[:500]
                            if item.get("about_me")
                            else "",
                        }
                    )
            except Exception as e:
                logger.error(f"StackOverflow search error: {e}")

        return candidates

    @staticmethod
    def search_internal(
        db: Session, keywords: dict, recruiter_id: int, max_count: int
    ) -> list:
        skill_list = keywords.get("skills", [])
        role_list = keywords.get("roles", [])
        candidates = []

        query = (
            db.query(Application)
            .join(User, Application.user_id == User.id)
            .filter(
                Application.deleted_at.is_(None),
                Application.status.in_(["pending", "screening"]),
            )
        )

        if skill_list:
            skill_filters = []
            for skill in skill_list[:3]:
                skill_filters.append(Application.cv_text_anonymized.ilike(f"%{skill}%"))
            if skill_filters:
                from sqlalchemy import or_

                query = query.filter(or_(*skill_filters))

        if role_list:
            role_filters = []
            for role in role_list[:3]:
                role_filters.append(Application.declared_role.ilike(f"%{role}%"))
            if role_filters:
                from sqlalchemy import or_

                query = query.filter(or_(*role_filters))

        for app in query.limit(max_count).all():
            user = app.owner
            if not user:
                continue

            existing = (
                db.query(SourcedCandidate)
                .filter(
                    SourcedCandidate.recruiter_id == recruiter_id,
                    SourcedCandidate.source == "internal",
                    SourcedCandidate.source_id == str(app.id),
                )
                .first()
            )
            if existing:
                continue

            candidates.append(
                {
                    "source_id": str(app.id),
                    "name": get_user_name(user) or app.full_name or "Unknown",
                    "headline": get_user_headline(user) or app.declared_role or "",
                    "location": user.location or "",
                    "profile_url": "",
                    "avatar_url": user.avatar_url or "",
                    "skills": get_user_skills(user) or "",
                    "bio": get_user_bio(user) or "",
                }
            )

        return candidates

    @staticmethod
    async def score_candidate(candidate_data: dict, job: Job) -> dict:
        prompt = f"""
You are an expert recruiter. Score this candidate's fit for the job.

Job Title: {job.title}
Job Skills: {job.required_skills}
Job Description: {job.description[:1500]}

Candidate Name: {candidate_data.get("name", "Unknown")}
Headline: {candidate_data.get("headline", "")}
Location: {candidate_data.get("location", "")}
Skills: {candidate_data.get("skills", "")}
Bio: {candidate_data.get("bio", "")}

Return JSON with:
- score (0-100 integer): overall match score
- reasoning (string): brief explanation of the score
- strengths (array of strings): top 3 strengths
- gaps (array of strings): top 3 gaps or missing areas
"""
        try:
            result = await call_groq_cascade(
                [{"role": "user", "content": prompt}], json_mode=True, temperature=0.2
            )
            if isinstance(result, dict):
                return {
                    "score": min(100, max(0, result.get("score", 0))),
                    "reasoning": result.get("reasoning", ""),
                    "strengths": result.get("strengths", []),
                    "gaps": result.get("gaps", []),
                }
            return {
                "score": 0,
                "reasoning": "AI scoring unavailable",
                "strengths": [],
                "gaps": [],
            }
        except Exception as e:
            logger.error(f"Candidate scoring failed: {e}")
            return {
                "score": 0,
                "reasoning": f"Scoring error: {str(e)}",
                "strengths": [],
                "gaps": [],
            }
