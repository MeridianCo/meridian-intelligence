from typing import Optional
from pydantic import BaseModel, AnyHttpUrl, Field

class enrich_request(BaseModel):
    linkedin_url: Optional[AnyHttpUrl] = None
    twitter_handle: Optional[str] = None
    github_username: Optional[str] = None


class event_search_request(BaseModel):
    city: str = Field(..., min_length=2, description="Primary city to match.")
    interests: list[str] = Field(
        default_factory=list,
        description="Topics, industries, hobbies, or formats to look for.",
    )
    nearby_locations: list[str] = Field(
        default_factory=list,
        description="Nearby neighborhoods or cities that should also count.",
    )
    source_urls: list[AnyHttpUrl] = Field(
        default_factory=list,
        description="Blog or local listing URLs to scrape for events.",
    )
    max_results: int = Field(default=10, ge=1, le=50)
