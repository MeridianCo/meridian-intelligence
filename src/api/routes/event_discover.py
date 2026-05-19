from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.middleware.auth import verify_bearer_token, limiter
from src.models.event_discovery import EventDiscoveryQuery, EventDiscoveryResponse
from src.services.events.discovery.event_discovery import EventDiscoveryService


router = APIRouter(
    dependencies=[Depends(verify_bearer_token)]
)
service = EventDiscoveryService()

def _normalize_and_validate(request: EventDiscoveryQuery) -> EventDiscoveryQuery:
    # Query string is required to keep results relevant and avoid expensive broad calls.
    if not (request.query and request.query.strip()):
        raise HTTPException(status_code=400, detail="query is required.")

    # Location is required to avoid broad/global provider queries that burn quota.
    has_geo = request.latitude is not None and request.longitude is not None
    has_city = bool(request.city and request.city.strip())
    if not (has_geo or has_city):
        raise HTTPException(status_code=400, detail="Provide either latitude/longitude or city.")

    # Default time window to keep results relevant + bounded when client omits dates.
    # (Client can always override.)
    if request.start_date is None and request.end_date is None:
        today = date.today()
        request.start_date = today
        request.end_date = date.fromordinal(today.toordinal() + 30)

    if request.start_date and request.end_date and request.end_date < request.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on/after start_date.")

    # If geo is used, radius must be reasonable.
    if has_geo:
        if request.radius_km < 1 or request.radius_km > 100:
            raise HTTPException(status_code=400, detail="radius_km must be between 1 and 100 for geo search.")

    return request


@router.get("/")
async def root():
    return {
        "service": "Event Discovery (API providers)",
        "endpoints": ["/events/discovery/search"],
        "enabled_providers": service.enabled_providers(),
        "available_providers": service.available_providers(),
    }


@router.get("/search", response_model=EventDiscoveryResponse)
# @limiter.limit("15/minute")
async def search_events_get(
    query: str | None = None,
    city: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: int = 25,
    start_date: date | None = None,
    end_date: date | None = None,
    cost: Annotated[str, Query(pattern="^(free|paid|any)$")] = "any",
    limit: int = 20,
    providers: str | None = None,
) -> EventDiscoveryResponse:
    provider_list = None
    if providers:
        provider_list = [part.strip() for part in providers.split(",") if part.strip()]
    request = EventDiscoveryQuery(
        query=query,
        city=city,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        start_date=start_date,
        end_date=end_date,
        cost=cost,  # type: ignore[arg-type]
        limit=limit,
        providers=provider_list,
    )
    request = _normalize_and_validate(request)
    return await service.search(request)


@router.post("/search", response_model=EventDiscoveryResponse)
# @limiter.limit("15/minute")
async def search_events_post(request: EventDiscoveryQuery) -> EventDiscoveryResponse:
    request = _normalize_and_validate(request)
    return await service.search(request)


@router.get("/providers/check")
# @limiter.limit("15/minute")
async def check_provider_keys():
    """Lightweight readiness check for provider credentials.

    This does not guarantee discovery/search access (e.g. Eventbrite may still restrict endpoints),
    but it helps catch missing environment variables quickly.
    """

    import os

    def present(name: str) -> bool:
        return bool(os.getenv(name))

    return {
        "serpapi_key_present": present("SERPAPI_API_KEY"),
        "eventbrite_token_present": present("EVENTBRITE_PRIVATE_TOKEN"),
        "ticketmaster_key_present": present("TICKETMASTER_API_KEY"),
        "enable_serpapi": os.getenv("EVENT_DISCOVERY_ENABLE_SERPAPI", ""),
        "enable_eventbrite": os.getenv("EVENT_DISCOVERY_ENABLE_EVENTBRITE", ""),
        "enable_ticketmaster": os.getenv("EVENT_DISCOVERY_ENABLE_TICKETMASTER", ""),
    }
