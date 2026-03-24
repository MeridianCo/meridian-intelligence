from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def root():
    return {
        "service": "Profile Enrichment API",
        "description": "Consolidates a user profile from various social sources such as LinkedIn, Twitter, and GitHub",
        "endpoints": ["/enrich/profile"]
    }

@router.get("/health")
async def health_check():
    return {"status": "ok"}

            # "/enrich/profile?linkedin_url=...&twitter_handle=...&github_username=..."

@router.get("/profile")
async def enrich_profile(linkedin_url: str = None, twitter_handle: str = None, github_username: str = None):
    #TODO: implement enrichment logic here
    return {"message": "Enriching profile with provided social URLs/handles..."}
    