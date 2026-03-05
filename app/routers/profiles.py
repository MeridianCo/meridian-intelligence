"""Profiles API router.

Endpoints
---------
POST /profiles/enrich   – Consolidate & enrich a professional profile.
GET  /profiles/health   – Simple liveness check for this router.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.schemas import ProfileRequest, ProfileResponse
from app.services.enricher import ProfileEnricher
from app.services.linkedin import LinkedInService
from app.services.web_scraper import WebScraperService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _get_enricher(settings: Settings = Depends(get_settings)) -> ProfileEnricher:
    """FastAPI dependency that builds a ``ProfileEnricher`` for each request."""
    return ProfileEnricher(
        settings=settings,
        linkedin_service=LinkedInService(settings),
        web_scraper=WebScraperService(settings),
    )


@router.post(
    "/enrich",
    response_model=ProfileResponse,
    summary="Consolidate and enrich a professional profile",
    description=(
        "Accepts a LinkedIn URL and/or a person's name, fetches data from all "
        "configured sources (LinkedIn via Proxycurl, public web pages), and "
        "returns a unified enriched profile."
    ),
    status_code=status.HTTP_200_OK,
)
async def enrich_profile(
    request: ProfileRequest,
    enricher: ProfileEnricher = Depends(_get_enricher),
) -> ProfileResponse:
    """Enrich and consolidate a professional profile from multiple sources."""
    logger.info(
        "Enrich request – linkedin_url=%s full_name=%s web_urls=%d",
        request.linkedin_url,
        request.full_name,
        len(request.web_urls),
    )
    try:
        return await enricher.enrich(request)
    except Exception as exc:
        logger.exception("Unexpected error during profile enrichment")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get(
    "/health",
    summary="Health check",
    description="Returns 200 OK when the profiles service is ready.",
)
async def health() -> dict:
    return {"status": "ok"}
