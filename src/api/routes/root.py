from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def root():
    return {
        "service": "AI Profile Intelligience Engine API",
        "version": "1.0",
        "description": "Consolidates a user profile from various social sources such as LinkedIn, Twitter, and GitHub",
        "endpoints": {
            "enrich": [
                "/enrich/profile?linkedin_url=...&twitter_handle=...&github_username=..."
            ],
            "health": ["/health"],
            "event_discovery_api_providers": ["/event-discovery/search"],
            "event_discovery_blog_scraper": ["/events/search"],
        },
    }

@router.get("/health")
async def health_check():
    return {"status": "ok"}
