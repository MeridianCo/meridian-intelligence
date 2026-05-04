from fastapi import APIRouter, HTTPException

from src.models.param_types import event_search_request
from src.services.events import BlogSource, EventSearch, candidate_to_dict, scrape_matching_events

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
    if not request.source_urls:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one blog or event listing URL in source_urls.",
        )

    search = EventSearch(
        city=request.city,
        interests=request.interests,
        nearby_locations=request.nearby_locations,
        sources=[BlogSource(url=str(url)) for url in request.source_urls],
        max_results=request.max_results,
    )

    try:
        candidates = scrape_matching_events(search)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unable to scrape source URLs: {exc}") from exc

    return {
        "city": request.city,
        "interests": request.interests,
        "count": len(candidates),
        "events": [candidate_to_dict(candidate) for candidate in candidates],
    }
