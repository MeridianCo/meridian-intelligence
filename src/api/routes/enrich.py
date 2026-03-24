from fastapi import APIRouter
from models.param_types import enrich_request

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

@router.get("/profile")
async def enrich_profile(request: enrich_request):
    #TODO: implement enrichment logic here
    return {"message": "Enriching profile with provided social URLs/handles..."}
    