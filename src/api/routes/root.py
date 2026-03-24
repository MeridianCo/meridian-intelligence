from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def root():
    {
    "service": "AI Profile Intelligience Engine API",
    "version": "1.0",
    "description": "Consolidates a user profile from various social sources such as LinkedIn, Twitter, and GitHub",
    "endpoints": {
        "enrich": [
            "/enrich/profile?linkedin_url=...&twitter_handle=...&github_username=..."
        ],
        "health": [
            "/health"
        ]
    }
}

@router.get("/health")
async def health_check():
    return {"status": "ok"}