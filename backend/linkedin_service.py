from typing import Optional

import httpx

from backend.logger import logger


class LinkedInService:
    API_BASE = "https://api.linkedin.com"
    OAUTH_BASE = "https://www.linkedin.com/oauth/v2"

    @staticmethod
    def get_oauth_url(client_id: str, redirect_uri: str, state: str) -> str:
        scopes = "openid profile email w_member_social r_organization_social rw_organization_admin"
        return (
            f"{LinkedInService.OAUTH_BASE}/authorization"
            f"?response_type=code"
            f"&client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&scope={scopes}"
            f"&state={state}"
        )

    @staticmethod
    async def exchange_code(
        code: str, client_id: str, client_secret: str, redirect_uri: str
    ) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{LinkedInService.OAUTH_BASE}/accessToken",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code != 200:
                logger.error(f"LinkedIn token exchange failed: {resp.text}")
                raise Exception("LinkedIn OAuth token exchange failed")

            return resp.json()

    @staticmethod
    async def refresh_access_token(
        refresh_token: str, client_id: str, client_secret: str
    ) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{LinkedInService.OAUTH_BASE}/accessToken",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code != 200:
                logger.error(f"LinkedIn token refresh failed: {resp.text}")
                raise Exception("LinkedIn token refresh failed")
            return resp.json()

    @staticmethod
    async def get_user_profile(access_token: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{LinkedInService.API_BASE}/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code != 200:
                logger.error(f"LinkedIn profile fetch failed: {resp.text}")
                raise Exception("Failed to fetch LinkedIn profile")
            return resp.json()

    @staticmethod
    async def get_organization(access_token: str, organization_urn: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{LinkedInService.API_BASE}/rest/organizations/{organization_urn}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "LinkedIn-Version": "202501",
                },
            )
            if resp.status_code != 200:
                logger.error(f"LinkedIn org fetch failed: {resp.text}")
                raise Exception("Failed to fetch LinkedIn organization")
            return resp.json()

    @staticmethod
    async def post_job(access_token: str, job_data: dict) -> dict:
        """
        Post a job to LinkedIn via Job Writes API.
        job_data should contain: company_urn, poster_urn, title, description,
        location, employment_type, salary_info
        """
        async with httpx.AsyncClient(timeout=30) as client:
            payload = {
                "author": job_data.get("poster_urn"),
                "lifecycleState": "PUBLISHED",
                "targetEntity": "urn:li:organization:"
                + job_data.get("company_urn", ""),
                "content": {
                    "title": job_data.get("title"),
                    "description": job_data.get("description"),
                },
                "jobPostingOperationType": "POST_JOB",
            }

            if job_data.get("location"):
                payload["content"]["location"] = job_data["location"]

            if job_data.get("employmentType"):
                payload["content"]["employmentType"] = job_data["employmentType"]

            resp = await client.post(
                f"{LinkedInService.API_BASE}/rest/jobs",
                json=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "LinkedIn-Version": "202501",
                    "X-Restli-Protocol-Version": "2.0.0",
                    "Content-Type": "application/json",
                },
            )

            if resp.status_code not in (200, 201):
                logger.error(
                    f"LinkedIn job post failed ({resp.status_code}): {resp.text}"
                )
                return {
                    "status": "error",
                    "detail": resp.text,
                    "status_code": resp.status_code,
                }

            job_urn = resp.headers.get("x-restli-id", "")
            return {
                "status": "posted",
                "job_urn": job_urn,
                "job_url": f"https://www.linkedin.com/jobs/view/{job_urn.split(':')[-1]}/"
                if job_urn
                else None,
            }

    @staticmethod
    async def import_profile(access_token: str, profile_url: str) -> dict:
        """
        Import LinkedIn profile data using Profile API.
        Returns structured candidate data.
        """
        profile_id = LinkedInService._extract_profile_id(profile_url)
        if not profile_id:
            return {"status": "error", "detail": "Invalid LinkedIn profile URL"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{LinkedInService.API_BASE}/v2/people/(id:{profile_id})",
                params={
                    "projection": "(id,firstName,lastName,headline,profilePicture,"
                    "location,industry,summary,skills,positions,education)"
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if resp.status_code != 200:
                logger.error(f"LinkedIn profile import failed: {resp.text}")
                return {"status": "error", "detail": "Failed to import profile"}

            data = resp.json()

            first_name = ""
            last_name = ""
            if data.get("firstName"):
                first_name = data["firstName"].get("localized", {}).get("en_US", "")
            if data.get("lastName"):
                last_name = data["lastName"].get("localized", {}).get("en_US", "")

            positions = []
            for pos in data.get("positions", {}).get("values", []):
                positions.append(
                    {
                        "title": pos.get("title", ""),
                        "company": pos.get("company", {}).get("name", ""),
                        "start": f"{pos.get('startDate', {}).get('year', '')}",
                        "end": f"{pos.get('endDate', {}).get('year', 'Present') if pos.get('isCurrent') else pos.get('endDate', {}).get('year', '')}",
                    }
                )

            education = []
            for edu in data.get("education", {}).get("values", []):
                education.append(
                    {
                        "school": edu.get("schoolName", ""),
                        "degree": edu.get("degreeName", ""),
                        "field": edu.get("fieldOfStudy", ""),
                    }
                )

            skills = []
            for skill in data.get("skills", {}).get("values", []):
                skills.append(skill.get("name", ""))

            return {
                "status": "ok",
                "profile": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "full_name": f"{first_name} {last_name}".strip(),
                    "headline": data.get("headline", ""),
                    "location": data.get("location", {}).get("name", ""),
                    "industry": data.get("industry", ""),
                    "summary": data.get("summary", ""),
                    "positions": positions,
                    "education": education,
                    "skills": skills,
                    "profile_picture": data.get("profilePicture", {}).get(
                        "displayImage", ""
                    ),
                },
            }

    @staticmethod
    async def search_company(access_token: str, company_name: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{LinkedInService.API_BASE}/rest/organizations",
                params={"q": "search", "search": company_name},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "LinkedIn-Version": "202501",
                },
            )
            if resp.status_code != 200:
                logger.error(f"LinkedIn company search failed: {resp.text}")
                return {"status": "error", "detail": "Company search failed"}

            data = resp.json()
            companies = []
            for elem in data.get("elements", []):
                companies.append(
                    {
                        "urn": elem.get("id", ""),
                        "name": elem.get("name", ""),
                        "vanity_name": elem.get("vanityName", ""),
                        "logo_url": elem.get("logoV2", {})
                        .get("original", {})
                        .get("url", ""),
                    }
                )

            return {"status": "ok", "companies": companies}

    @staticmethod
    def _extract_profile_id(profile_url: str) -> Optional[str]:
        import re

        patterns = [
            r"linkedin\.com/in/([^/?#]+)",
            r"linkedin\.com/pub/([^/?#]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, profile_url)
            if match:
                return match.group(1)
        return None
