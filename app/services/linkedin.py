"""LinkedIn profile fetching service.

Uses the Proxycurl API when an API key is configured, otherwise returns an
empty partial profile so the rest of the enrichment pipeline can still run.

Proxycurl docs: https://nubela.co/proxycurl/docs
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Settings
from app.models import (
    DateRange,
    Education,
    Profile,
    ProfileSource,
    Skill,
    SocialLinks,
    WorkExperience,
)

logger = logging.getLogger(__name__)

_PROXYCURL_PERSON_URL = "https://nubela.co/proxycurl/api/v2/linkedin"


def _parse_date(value: Optional[dict]) -> Optional[str]:
    """Convert a Proxycurl date dict ``{year, month, day}`` to an ISO date string."""
    if not value:
        return None
    year = value.get("year")
    if not year:
        return None
    month = value.get("month") or 1
    day = value.get("day") or 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def _build_date_range(start: Optional[dict], end: Optional[dict]) -> Optional[DateRange]:
    start_str = _parse_date(start)
    end_str = _parse_date(end)
    if not start_str and not end_str:
        return None
    return DateRange(
        start=start_str or None,
        end=end_str or None,
        is_current=end_str is None,
    )


def _parse_proxycurl_response(data: dict) -> Profile:
    """Parse a Proxycurl person-profile response into our domain ``Profile``."""
    work_experience: list[WorkExperience] = []
    for exp in data.get("experiences", []) or []:
        work_experience.append(
            WorkExperience(
                title=exp.get("title") or "Unknown",
                company=exp.get("company") or "Unknown",
                location=exp.get("location"),
                description=exp.get("description"),
                date_range=_build_date_range(exp.get("starts_at"), exp.get("ends_at")),
                source=ProfileSource.LINKEDIN,
            )
        )

    education: list[Education] = []
    for edu in data.get("education", []) or []:
        education.append(
            Education(
                institution=edu.get("school") or "Unknown",
                degree=edu.get("degree_name"),
                field_of_study=edu.get("field_of_study"),
                date_range=_build_date_range(edu.get("starts_at"), edu.get("ends_at")),
                source=ProfileSource.LINKEDIN,
            )
        )

    skills: list[Skill] = [
        Skill(name=s, source=ProfileSource.LINKEDIN)
        for s in (data.get("skills") or [])
    ]

    social_links = SocialLinks(
        linkedin=data.get("public_identifier")
        and f"https://linkedin.com/in/{data['public_identifier']}",
        twitter=data.get("twitter_handle")
        and f"https://twitter.com/{data['twitter_handle']}",
        github=data.get("github_profile_url"),
        website=data.get("website"),
    )

    return Profile(
        full_name=data.get("full_name"),
        headline=data.get("headline"),
        summary=data.get("summary"),
        location=data.get("city") or data.get("country_full_name"),
        email=data.get("personal_emails", [None])[0] if data.get("personal_emails") else None,
        social_links=social_links,
        work_experience=work_experience,
        education=education,
        skills=skills,
        sources_used=[ProfileSource.LINKEDIN],
    )


class LinkedInService:
    """Fetches and parses LinkedIn profile data via Proxycurl."""

    def __init__(self, settings: Settings, client: Optional[httpx.AsyncClient] = None) -> None:
        self._settings = settings
        self._client = client  # injected for testing

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _get(self, url: str, params: dict) -> dict:
        headers = {"Authorization": f"Bearer {self._settings.proxycurl_api_key}"}
        if self._client:
            response = await self._client.get(url, params=params, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self._settings.http_timeout) as client:
                response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    async def fetch_by_url(self, linkedin_url: str) -> Profile:
        """Return an enriched ``Profile`` for the given LinkedIn profile URL."""
        if not self._settings.proxycurl_api_key:
            logger.warning("proxycurl_api_key not configured – skipping LinkedIn fetch.")
            return Profile()

        try:
            data = await self._get(
                _PROXYCURL_PERSON_URL,
                {"url": linkedin_url, "extra": "include", "skills": "include"},
            )
            return _parse_proxycurl_response(data)
        except httpx.HTTPStatusError as exc:
            logger.error("Proxycurl returned %s for %s", exc.response.status_code, linkedin_url)
            raise
        except httpx.RequestError as exc:
            logger.error("Network error fetching LinkedIn profile: %s", exc)
            raise

    async def fetch_by_name(self, full_name: str, company: Optional[str] = None) -> Profile:
        """Best-effort name-based LinkedIn lookup via Proxycurl's search endpoint."""
        if not self._settings.proxycurl_api_key:
            logger.warning("proxycurl_api_key not configured – skipping LinkedIn name search.")
            return Profile()

        search_url = "https://nubela.co/proxycurl/api/linkedin/profile/search/person"
        params: dict = {"first_name": full_name.split()[0], "page_size": 1}
        if len(full_name.split()) > 1:
            params["last_name"] = " ".join(full_name.split()[1:])
        if company:
            params["current_company_name"] = company

        try:
            search_data = await self._get(search_url, params)
            results = search_data.get("results") or []
            if not results:
                return Profile(full_name=full_name)
            linkedin_url = results[0].get("linkedin_profile_url")
            if not linkedin_url:
                return Profile(full_name=full_name)
            return await self.fetch_by_url(linkedin_url)
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.error("LinkedIn name search failed: %s", exc)
            raise
