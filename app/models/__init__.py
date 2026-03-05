"""Pydantic models for professional profile data."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import AnyHttpUrl, BaseModel, Field


class ProfileSource(str, Enum):
    """Supported data sources for profile enrichment."""

    LINKEDIN = "linkedin"
    WEB = "web"
    CLEARBIT = "clearbit"
    MANUAL = "manual"


class DateRange(BaseModel):
    """An optional date range used by work experience and education entries."""

    start: Optional[date] = None
    end: Optional[date] = None
    is_current: bool = False


class WorkExperience(BaseModel):
    """A single professional role."""

    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    date_range: Optional[DateRange] = None
    source: ProfileSource = ProfileSource.MANUAL


class Education(BaseModel):
    """A single education entry."""

    institution: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    date_range: Optional[DateRange] = None
    source: ProfileSource = ProfileSource.MANUAL


class Skill(BaseModel):
    """A professional skill, optionally with an endorsement count."""

    name: str
    endorsements: int = 0
    source: ProfileSource = ProfileSource.MANUAL


class SocialLinks(BaseModel):
    """Collection of social / professional profile URLs."""

    linkedin: Optional[AnyHttpUrl] = None
    twitter: Optional[AnyHttpUrl] = None
    github: Optional[AnyHttpUrl] = None
    website: Optional[AnyHttpUrl] = None


class Profile(BaseModel):
    """A unified, enriched professional profile."""

    # Identity
    full_name: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    location: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    # Social presence
    social_links: SocialLinks = Field(default_factory=SocialLinks)

    # Professional history
    work_experience: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)

    # Derived / enriched metadata
    sources_used: list[ProfileSource] = Field(default_factory=list)
    raw_web_snippets: list[str] = Field(
        default_factory=list,
        description="Raw text snippets gathered from public web pages.",
    )
