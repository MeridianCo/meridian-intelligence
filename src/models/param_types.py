from typing import Optional
from pydantic import BaseModel, AnyHttpUrl

class enrich_request(BaseModel):
    linkedin_url: Optional[AnyHttpUrl] = None
    twitter_handle: Optional[str] = None
    github_username: Optional[str] = None