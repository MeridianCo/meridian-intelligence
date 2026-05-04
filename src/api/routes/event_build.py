from fastapi import APIRouter, HTTPException

from src.models.param_types import event_search_request
from src.services.events import BlogSource, EventSearch, candidate_to_dict, discover_event_sources, scrape_matching_events

router = APIRouter()


@router.get("/")
async def root():
    return {
        "service": "Event Discovery API",
        "description": "Scrapes local blogs and listing pages for city-matched events.",
        "endpoints": ["/events/search"],
    }


@router.post("/search")
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
        discovered_sources = discover_event_sources(search)[: request.max_discovered_sources]
        candidates = scrape_matching_events(search)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unable to scrape source URLs: {exc}") from exc

    return {
        "city": request.city,
        "interests": request.interests,
        "discovered_sources": [
            {"url": source.url, "name": source.name, "score": source.discovery_score}
            for source in discovered_sources
        ],
        "count": len(candidates),
        "events": [candidate_to_dict(candidate) for candidate in candidates],
    }
