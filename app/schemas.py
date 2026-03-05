"""Request and response schemas for the profiles API."""

from __future__ import annotations

from typing import Optional

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator

from app.models import Profile


class ProfileRequest(BaseModel):
    """Input schema for a profile consolidation request.

    At least one of ``linkedin_url`` or ``full_name`` must be provided.
    When ``full_name`` is supplied, providing ``company`` improves match quality.
    Additional ``web_urls`` can be given to pull in extra public pages.
    """

    linkedin_url: Optional[AnyHttpUrl] = Field(
        default=None,
        description="Public LinkedIn profile URL, e.g. https://linkedin.com/in/johndoe",
    )
    full_name: Optional[str] = Field(
        default=None,
        description="Full name of the person to look up.",
    )
    company: Optional[str] = Field(
        default=None,
        description="Current or most-recent employer – improves name-based lookup.",
    )
    web_urls: list[AnyHttpUrl] = Field(
        default_factory=list,
        description="Additional public web pages to scrape (personal site, bio page, etc.).",
    )

    @model_validator(mode="after")
    def _require_identifier(self) -> "ProfileRequest":
        if not self.linkedin_url and not self.full_name:
            raise ValueError("Provide at least one of 'linkedin_url' or 'full_name'.")
        return self


class ProfileResponse(BaseModel):
    """Enriched profile returned by the API."""

    profile: Profile
    sources_used: list[str] = Field(default_factory=list)
    errors: list[str] = Field(
        default_factory=list,
        description="Non-fatal errors encountered while fetching data.",
    )
