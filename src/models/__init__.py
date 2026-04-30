"""models for profile data."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import AnyHttpUrl, BaseModel, Field

class ProfileSource(str, Enum):
    LINKEDIN = "linkedin"
    GITHUB = "github"
    
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    THREADS = "threads"
    FACEBOOK = "facebook"
    
    WEB = "web"
    MANUAL = "manual"


class DateRange(BaseModel):
    start: Optional[date] = None
    end: Optional[date] = None
    is_current: bool = False

class WorkExperience(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    date_range: Optional[DateRange] = None
    source: ProfileSource = ProfileSource.MANUAL


class Education(BaseModel):
    institution: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    date_range: Optional[DateRange] = None
    source: ProfileSource = ProfileSource.MANUAL


class Skill(BaseModel):
    name: str
    endorsements: int = 0
    source: ProfileSource = ProfileSource.MANUAL

class SocialLinks(BaseModel):
    linkedin: Optional[AnyHttpUrl] = None
    twitter: Optional[AnyHttpUrl] = None
    instagram: Optional[AnyHttpUrl] = None
    threads: Optional[AnyHttpUrl] = None
    facebook: Optional[AnyHttpUrl] = None
    github: Optional[AnyHttpUrl] = None
    website: Optional[AnyHttpUrl] = None


class Profile(BaseModel):
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