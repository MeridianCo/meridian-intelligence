"""Profile enrichment and consolidation service.

Orchestrates LinkedIn and web-scraping services to produce a single, unified
``Profile`` for a given request.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import Settings
from app.models import Profile, ProfileSource
from app.schemas import ProfileRequest, ProfileResponse
from app.services.linkedin import LinkedInService
from app.services.web_scraper import WebScraperService

logger = logging.getLogger(__name__)


def _merge_profiles(base: Profile, overlay: Profile) -> Profile:
    """Merge ``overlay`` into ``base``, preferring non-None values from overlay."""
    data = base.model_dump()
    overlay_data = overlay.model_dump(exclude_none=True)

    # Scalar fields: overlay wins when present
    for field in ("full_name", "headline", "summary", "location", "email", "phone"):
        if overlay_data.get(field):
            data[field] = overlay_data[field]

    # Social links: overlay wins per-field
    if overlay_data.get("social_links"):
        for link_field, link_val in overlay_data["social_links"].items():
            if link_val:
                data["social_links"][link_field] = link_val

    # Lists: concatenate and deduplicate by a key
    def _dedup_by(items: list[dict], key: str) -> list[dict]:
        seen: set = set()
        result: list[dict] = []
        for item in items:
            k = item.get(key, "")
            if k not in seen:
                seen.add(k)
                result.append(item)
        return result

    data["work_experience"] = _dedup_by(
        data["work_experience"] + overlay_data.get("work_experience", []),
        "title",
    )
    data["education"] = _dedup_by(
        data["education"] + overlay_data.get("education", []),
        "institution",
    )

    # Skills: deduplicate by name, favour higher endorsement count
    skill_map: dict[str, dict] = {s["name"]: s for s in data["skills"]}
    for skill in overlay_data.get("skills", []):
        name = skill["name"]
        if name not in skill_map or skill.get("endorsements", 0) > skill_map[name].get("endorsements", 0):
            skill_map[name] = skill
    data["skills"] = list(skill_map.values())

    # Sources + snippets: union
    merged_sources = list(
        {s for s in data["sources_used"] + overlay_data.get("sources_used", [])}
    )
    data["sources_used"] = merged_sources
    data["raw_web_snippets"] = data["raw_web_snippets"] + overlay_data.get("raw_web_snippets", [])

    return Profile.model_validate(data)


class ProfileEnricher:
    """Consolidates profile data from multiple sources into a single ``Profile``."""

    def __init__(
        self,
        settings: Settings,
        linkedin_service: Optional[LinkedInService] = None,
        web_scraper: Optional[WebScraperService] = None,
    ) -> None:
        self._settings = settings
        self._linkedin = linkedin_service or LinkedInService(settings)
        self._scraper = web_scraper or WebScraperService(settings)

    async def enrich(self, request: ProfileRequest) -> ProfileResponse:
        """Run all configured enrichment sources and return a consolidated response."""
        profile = Profile()
        errors: list[str] = []

        # --- LinkedIn ---
        if request.linkedin_url:
            try:
                linkedin_profile = await self._linkedin.fetch_by_url(str(request.linkedin_url))
                profile = _merge_profiles(profile, linkedin_profile)
            except Exception as exc:  # noqa: BLE001
                msg = f"LinkedIn fetch failed: {exc}"
                logger.warning(msg)
                errors.append(msg)
        elif request.full_name:
            try:
                linkedin_profile = await self._linkedin.fetch_by_name(
                    request.full_name, request.company
                )
                profile = _merge_profiles(profile, linkedin_profile)
            except Exception as exc:  # noqa: BLE001
                msg = f"LinkedIn name search failed: {exc}"
                logger.warning(msg)
                errors.append(msg)

        # Seed name/company from request when LinkedIn returned nothing
        if not profile.full_name and request.full_name:
            profile = profile.model_copy(update={"full_name": request.full_name})

        # --- Web scraping ---
        web_urls = [str(u) for u in request.web_urls]
        if web_urls:
            try:
                snippets = await self._scraper.scrape_many(web_urls)
                if snippets:
                    profile = _merge_profiles(
                        profile,
                        Profile(
                            raw_web_snippets=snippets,
                            sources_used=[ProfileSource.WEB],
                        ),
                    )
            except Exception as exc:  # noqa: BLE001
                msg = f"Web scraping failed: {exc}"
                logger.warning(msg)
                errors.append(msg)

        sources_used = [s.value for s in profile.sources_used]

        return ProfileResponse(
            profile=profile,
            sources_used=sources_used,
            errors=errors,
        )
