from fastapi import APIRouter, HTTPException, Depends

from src.db.event_store import save_event_candidates
from src.models.param_types import event_search_request
from src.services.events.scrape import (
    BlogSource,
    EventSearch,
    candidate_to_dict,
    scrape_events,
    source_reliability_to_dict,
)
from src.api.middleware.auth import verify_bearer_token, limiter

router = APIRouter(
    dependencies=[Depends(verify_bearer_token)],
)

@router.get("/")
async def root():
    return {
        "service": "Event Discovery API",
        "description": "Scrapes local blogs and listing pages for city-matched events.",
        "endpoints": ["/events/search"],
    }


@router.post("/search")
@limiter.limit("15/minute")
async def search_events(request: event_search_request):
    if not request.source_urls and not request.seed_urls:
        raise HTTPException(
            status_code=400,
            detail="Provide source_urls to scrape or seed_urls to discover event sources.",
        )

    search = EventSearch(
        city=request.city,
        interests=request.interests,
        nearby_locations=request.nearby_locations,
        sources=[BlogSource(url=str(url)) for url in request.source_urls],
        seed_urls=[str(url) for url in request.seed_urls] if request.discover_sources else [],
        max_discovered_sources=request.max_discovered_sources,
        max_results=request.max_results,
    )

    try:
        result = scrape_events(search)
        candidates = result.events
        saved_events = save_event_candidates(candidates) if request.persist_results else []
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unable to scrape source URLs: {exc}") from exc

    return {
        "city": request.city,
        "interests": request.interests,
        "discovered_sources": [
            {"url": source.url, "name": source.name, "score": source.discovery_score}
            for source in result.discovered_sources
        ],
        "source_reliability": [
            source_reliability_to_dict(source) for source in result.source_reliability
        ],
        "count": len(candidates),
        "saved_count": len(saved_events),
        "events": [candidate_to_dict(candidate) for candidate in candidates],
    }
