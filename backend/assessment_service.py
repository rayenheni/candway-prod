import hashlib
import hmac
import json

import httpx

from backend.config import get_settings
from backend.database import Assessment, AssessmentInvitation
from backend.email_service import email_service, wrap_in_template
from backend.logger import logger

settings = get_settings()


class AssessmentService:
    PROVIDERS = {
        "hackerrank": {
            "api_base": "https://www.hackerrank.com/api/v3",
            "tests_endpoint": "/tests",
            "candidates_endpoint": "/tests/{test_id}/candidates",
            "results_endpoint": "/tests/{test_id}/results",
        },
        "codility": {
            "api_base": "https://api.codility.com/api/v1",
            "tests_endpoint": "/tests",
            "candidates_endpoint": "/tests/{test_id}/candidates",
            "results_endpoint": "/results",
        },
    }

    @staticmethod
    def _get_api_key(provider: str) -> str:
        if provider == "hackerrank":
            return settings.hackerrank_api_key or ""
        elif provider == "codility":
            return settings.codility_api_key or ""
        return ""

    @staticmethod
    def _get_webhook_secret(provider: str) -> str:
        if provider == "hackerrank":
            return settings.hackerrank_webhook_secret or ""
        elif provider == "codility":
            return settings.codility_webhook_secret or ""
        return ""

    @staticmethod
    def _get_headers(provider: str) -> dict:
        api_key = AssessmentService._get_api_key(provider)
        if provider == "hackerrank":
            return {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        elif provider == "codility":
            return {
                "Authorization": api_key,
                "Content-Type": "application/json",
            }
        return {}

    @staticmethod
    async def create_assessment(
        provider: str,
        job_id: int,
        recruiter_id: int,
        test_name: str,
        difficulty: str,
        duration_minutes: int,
        skills: list,
        db,
    ) -> dict:
        provider_config = AssessmentService.PROVIDERS.get(provider)
        if not provider_config:
            raise ValueError(f"Unsupported provider: {provider}")

        api_key = AssessmentService._get_api_key(provider)
        if not api_key:
            raise ValueError(f"API key not configured for provider: {provider}")

        url = f"{provider_config['api_base']}{provider_config['tests_endpoint']}"
        headers = AssessmentService._get_headers(provider)

        if provider == "hackerrank":
            payload = {
                "name": test_name,
                "duration": duration_minutes,
                "difficulty": difficulty,
                "skills": skills,
            }
        elif provider == "codility":
            payload = {
                "title": test_name,
                "time": duration_minutes,
                "difficulty": difficulty,
                "skills": skills,
            }
        else:
            payload = {}

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=30)
            if resp.status_code not in (200, 201):
                logger.error(
                    f"Assessment creation failed [{provider}]: {resp.status_code} {resp.text}"
                )
                raise Exception(
                    f"Failed to create assessment on {provider}: {resp.text}"
                )
            data = resp.json()

        provider_test_id = None
        if provider == "hackerrank":
            provider_test_id = str(data.get("id") or data.get("data", {}).get("id", ""))
        elif provider == "codility":
            provider_test_id = str(data.get("id") or data.get("test_id", ""))

        assessment = Assessment(
            recruiter_id=recruiter_id,
            job_id=job_id,
            provider=provider,
            provider_test_id=provider_test_id,
            test_name=test_name,
            difficulty=difficulty,
            duration_minutes=duration_minutes,
            skills=json.dumps(skills) if skills else None,
            status="active",
        )
        db.add(assessment)
        db.commit()
        db.refresh(assessment)

        return {
            "id": assessment.id,
            "provider_test_id": provider_test_id,
            "test_name": test_name,
            "provider": provider,
            "status": "active",
        }

    @staticmethod
    async def invite_candidate(
        provider: str,
        test_id: str,
        application_id: int,
        candidate_email: str,
        candidate_name: str,
        send_email: bool = True,
        db=None,
    ) -> dict:
        provider_config = AssessmentService.PROVIDERS.get(provider)
        if not provider_config:
            raise ValueError(f"Unsupported provider: {provider}")

        url = f"{provider_config['api_base']}{provider_config['candidates_endpoint'].format(test_id=test_id)}"
        headers = AssessmentService._get_headers(provider)

        if provider == "hackerrank":
            payload = {
                "email": candidate_email,
                "name": candidate_name,
                "send_email": send_email,
            }
        elif provider == "codility":
            payload = {
                "email": candidate_email,
                "name": candidate_name,
                "send_invitation": send_email,
            }
        else:
            payload = {}

        invite_url = None
        provider_candidate_id = None

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=30)
            if resp.status_code not in (200, 201):
                logger.error(
                    f"Invite failed [{provider}]: {resp.status_code} {resp.text}"
                )
                raise Exception(
                    f"Failed to invite candidate on {provider}: {resp.text}"
                )
            data = resp.json()

            if provider == "hackerrank":
                provider_candidate_id = str(
                    data.get("id") or data.get("data", {}).get("id", "")
                )
                invite_url = data.get("invite_url") or data.get("data", {}).get(
                    "invite_url"
                )
            elif provider == "codility":
                provider_candidate_id = str(
                    data.get("id") or data.get("candidate_id", "")
                )
                invite_url = data.get("invite_url") or data.get("url", "")

        invitation = AssessmentInvitation(
            assessment_id=db.query(Assessment.id)
            .filter(Assessment.provider_test_id == test_id)
            .scalar()
            if not db
            else None,
            application_id=application_id,
            provider_candidate_id=provider_candidate_id,
            invite_url=invite_url,
            status="invited",
        )

        if not invitation.assessment_id:
            invitation.assessment_id = (
                db.query(Assessment.id)
                .filter(Assessment.provider_test_id == test_id)
                .scalar()
            )

        db.add(invitation)
        db.commit()
        db.refresh(invitation)

        if send_email and invite_url:
            subject = f"Assessment Invitation: {candidate_name}"
            content = f"""
            <h2 style="margin:0 0 16px;font-size:22px;font-weight:700;color:#1e293b;">Assessment Invitation</h2>
            <p style="margin:0 0 24px;color:#475569;font-size:15px;">
                Hello <strong>{candidate_name}</strong>,
            </p>
            <p style="margin:0 0 24px;color:#475569;font-size:15px;">
                You have been invited to complete an assessment. Please click the button below to start.
            </p>
            <p style="margin:24px 0;text-align:center;">
                <a href="{invite_url}" style="background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;padding:14px 28px;text-decoration:none;border-radius:10px;font-weight:600;font-size:15px;display:inline-block;">Start Assessment</a>
            </p>
            <p style="margin:24px 0 0;color:#94a3b8;font-size:14px;">
                This link is unique to you. Please do not share it with anyone.
            </p>
            """
            email_service.send_email(
                candidate_email, subject, wrap_in_template(content, subject)
            )

        return {
            "id": invitation.id,
            "invite_url": invite_url,
            "provider_candidate_id": provider_candidate_id,
            "status": "invited",
        }

    @staticmethod
    async def get_test_results(
        provider: str, test_id: str, candidate_test_id: str
    ) -> dict:
        provider_config = AssessmentService.PROVIDERS.get(provider)
        if not provider_config:
            raise ValueError(f"Unsupported provider: {provider}")

        url = f"{provider_config['api_base']}{provider_config['results_endpoint'].format(test_id=test_id)}"
        headers = AssessmentService._get_headers(provider)

        if candidate_test_id:
            url = f"{url}/{candidate_test_id}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                logger.error(
                    f"Results fetch failed [{provider}]: {resp.status_code} {resp.text}"
                )
                raise Exception(f"Failed to fetch results from {provider}: {resp.text}")
            return resp.json()

    @staticmethod
    async def handle_webhook(provider: str, payload: dict, db) -> dict:
        provider_config = AssessmentService.PROVIDERS.get(provider)
        if not provider_config:
            raise ValueError(f"Unsupported provider: {provider}")

        candidate_test_id = None
        test_id = None
        raw_results = {}

        if provider == "hackerrank":
            candidate_test_id = str(
                payload.get("candidate_test_id")
                or payload.get("data", {}).get("id", "")
            )
            test_id = str(
                payload.get("test_id") or payload.get("data", {}).get("test_id", "")
            )
            raw_results = payload.get("data", {}).get("results", payload)
        elif provider == "codility":
            candidate_test_id = str(
                payload.get("candidate_id") or payload.get("id", "")
            )
            test_id = str(payload.get("test_id") or payload.get("group_id", ""))
            raw_results = payload

        invitation = None
        if candidate_test_id:
            invitation = (
                db.query(AssessmentInvitation)
                .filter(AssessmentInvitation.provider_candidate_id == candidate_test_id)
                .first()
            )

        if not invitation and test_id:
            invitation = (
                db.query(AssessmentInvitation)
                .join(Assessment)
                .filter(
                    Assessment.provider_test_id == test_id,
                    AssessmentInvitation.status == "invited",
                )
                .first()
            )

        if not invitation:
            logger.warning(
                f"No matching invitation found for webhook: provider={provider}, candidate_test_id={candidate_test_id}"
            )
            return {"status": "ignored", "reason": "No matching invitation"}

        formatted = AssessmentService._format_results_for_scoring(provider, raw_results)

        invitation.status = "completed"
        invitation.score = formatted.get("score")
        invitation.max_score = formatted.get("max_score")
        invitation.skills_breakdown = (
            json.dumps(formatted.get("skills_breakdown"))
            if formatted.get("skills_breakdown")
            else None
        )
        invitation.duration_seconds = formatted.get("duration_seconds")
        invitation.plagiarism_flag = formatted.get("plagiarism_flag", False)
        invitation.completed_at = formatted.get("completed_at")
        db.commit()

        logger.info(
            f"Webhook processed for invitation {invitation.id}: score={formatted.get('score')}"
        )

        return {
            "status": "processed",
            "invitation_id": invitation.id,
            "score": formatted.get("score"),
            "plagiarism_flag": formatted.get("plagiarism_flag"),
        }

    @staticmethod
    def _format_results_for_scoring(provider: str, raw_results: dict) -> dict:
        result = {
            "score": None,
            "max_score": None,
            "skills_breakdown": None,
            "duration_seconds": None,
            "plagiarism_flag": False,
            "completed_at": None,
        }

        if provider == "hackerrank":
            result["score"] = raw_results.get("score")
            result["max_score"] = raw_results.get("max_score", 100)
            result["plagiarism_flag"] = raw_results.get(
                "plagiarism", False
            ) or raw_results.get("plagiarism_flag", False)
            result["duration_seconds"] = raw_results.get(
                "duration", raw_results.get("duration_seconds")
            )
            skills = raw_results.get("skills_breakdown") or raw_results.get(
                "skills", {}
            )
            if isinstance(skills, dict) and skills:
                result["skills_breakdown"] = skills
            elif isinstance(skills, str):
                try:
                    result["skills_breakdown"] = json.loads(skills)
                except (json.JSONDecodeError, TypeError):
                    pass

        elif provider == "codility":
            result["score"] = raw_results.get("score")
            result["max_score"] = raw_results.get("max_score", 100)
            result["plagiarism_flag"] = raw_results.get(
                "plagiarism_detected", False
            ) or raw_results.get("plagiarism_flag", False)
            result["duration_seconds"] = raw_results.get(
                "duration", raw_results.get("time_taken")
            )
            tasks = raw_results.get("tasks") or raw_results.get("results", [])
            if isinstance(tasks, list):
                skills_data = {}
                for t in tasks:
                    if isinstance(t, dict):
                        task_name = t.get("title") or t.get("name", "unknown")
                        skills_data[task_name] = t.get("score", 0)
                if skills_data:
                    result["skills_breakdown"] = skills_data

        return result

    @staticmethod
    def get_available_tests(provider: str, api_key: str) -> list:
        provider_config = AssessmentService.PROVIDERS.get(provider)
        if not provider_config:
            raise ValueError(f"Unsupported provider: {provider}")

        import requests

        url = f"{provider_config['api_base']}{provider_config['tests_endpoint']}"
        headers = {}

        if provider == "hackerrank":
            headers = {"Authorization": f"Bearer {api_key}"}
        elif provider == "codility":
            headers = {"Authorization": api_key}

        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                logger.error(
                    f"List tests failed [{provider}]: {resp.status_code} {resp.text}"
                )
                return []
            data = resp.json()
            tests = data.get("data", []) if isinstance(data, dict) else data
            if isinstance(tests, list):
                return tests
            return []
        except Exception as e:
            logger.error(f"Error listing tests from {provider}: {e}")
            return []

    @staticmethod
    def verify_webhook_signature(provider: str, payload: bytes, signature: str) -> bool:
        secret = AssessmentService._get_webhook_secret(provider)
        if not secret:
            logger.warning(
                f"No webhook secret configured for {provider}, skipping signature verification"
            )
            return True

        if provider == "hackerrank":
            expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, signature)
        elif provider == "codility":
            expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
            return hmac.compare_digest(f"sha256={expected}", signature)

        return True
