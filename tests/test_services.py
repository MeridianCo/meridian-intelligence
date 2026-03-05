"""Unit tests for services: LinkedIn, WebScraper, and ProfileEnricher."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.config import Settings
from app.models import Profile, ProfileSource, Skill, WorkExperience
from app.schemas import ProfileRequest
from app.services.enricher import ProfileEnricher, _merge_profiles
from app.services.linkedin import LinkedInService, _parse_proxycurl_response
from app.services.web_scraper import WebScraperService, _extract_text

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def settings_no_key() -> Settings:
    return Settings(proxycurl_api_key="", debug=True)


@pytest.fixture()
def settings_with_key() -> Settings:
    return Settings(proxycurl_api_key="test-key-123", debug=True)


SAMPLE_PROXYCURL_RESPONSE = {
    "full_name": "Jane Doe",
    "headline": "Senior Engineer at Acme",
    "summary": "Passionate engineer.",
    "city": "San Francisco",
    "public_identifier": "janedoe",
    "personal_emails": ["jane@example.com"],
    "experiences": [
        {
            "title": "Senior Engineer",
            "company": "Acme Corp",
            "location": "San Francisco, CA",
            "description": "Built things.",
            "starts_at": {"year": 2020, "month": 3, "day": 1},
            "ends_at": None,
        }
    ],
    "education": [
        {
            "school": "State University",
            "degree_name": "B.Sc.",
            "field_of_study": "Computer Science",
            "starts_at": {"year": 2014, "month": 9, "day": 1},
            "ends_at": {"year": 2018, "month": 6, "day": 1},
        }
    ],
    "skills": ["Python", "FastAPI", "PostgreSQL"],
}


# ---------------------------------------------------------------------------
# _parse_proxycurl_response
# ---------------------------------------------------------------------------

class TestParseProxycurlResponse:
    def test_basic_fields(self) -> None:
        profile = _parse_proxycurl_response(SAMPLE_PROXYCURL_RESPONSE)
        assert profile.full_name == "Jane Doe"
        assert profile.headline == "Senior Engineer at Acme"
        assert profile.location == "San Francisco"
        assert profile.email == "jane@example.com"

    def test_work_experience_parsed(self) -> None:
        profile = _parse_proxycurl_response(SAMPLE_PROXYCURL_RESPONSE)
        assert len(profile.work_experience) == 1
        exp = profile.work_experience[0]
        assert exp.title == "Senior Engineer"
        assert exp.company == "Acme Corp"
        assert exp.source == ProfileSource.LINKEDIN
        assert exp.date_range is not None
        assert exp.date_range.is_current is True

    def test_education_parsed(self) -> None:
        profile = _parse_proxycurl_response(SAMPLE_PROXYCURL_RESPONSE)
        assert len(profile.education) == 1
        edu = profile.education[0]
        assert edu.institution == "State University"
        assert edu.degree == "B.Sc."

    def test_skills_parsed(self) -> None:
        profile = _parse_proxycurl_response(SAMPLE_PROXYCURL_RESPONSE)
        names = [s.name for s in profile.skills]
        assert "Python" in names
        assert "FastAPI" in names

    def test_social_links_linkedin(self) -> None:
        profile = _parse_proxycurl_response(SAMPLE_PROXYCURL_RESPONSE)
        assert profile.social_links.linkedin is not None
        assert "janedoe" in str(profile.social_links.linkedin)

    def test_source_tagged_linkedin(self) -> None:
        profile = _parse_proxycurl_response(SAMPLE_PROXYCURL_RESPONSE)
        assert ProfileSource.LINKEDIN in profile.sources_used

    def test_empty_response(self) -> None:
        profile = _parse_proxycurl_response({})
        assert profile.full_name is None
        assert profile.work_experience == []
        assert profile.skills == []


# ---------------------------------------------------------------------------
# LinkedInService
# ---------------------------------------------------------------------------

class TestLinkedInServiceNoApiKey:
    @pytest.mark.asyncio
    async def test_fetch_by_url_returns_empty_profile(self, settings_no_key: Settings) -> None:
        svc = LinkedInService(settings_no_key)
        profile = await svc.fetch_by_url("https://linkedin.com/in/janedoe")
        assert isinstance(profile, Profile)
        assert profile.full_name is None

    @pytest.mark.asyncio
    async def test_fetch_by_name_returns_empty_profile(self, settings_no_key: Settings) -> None:
        svc = LinkedInService(settings_no_key)
        profile = await svc.fetch_by_name("Jane Doe", "Acme")
        assert isinstance(profile, Profile)


class TestLinkedInServiceWithMockedHttp:
    @pytest.mark.asyncio
    async def test_fetch_by_url_parses_response(self, settings_with_key: Settings) -> None:
        svc = LinkedInService(settings_with_key)
        with patch.object(svc, "_get", new=AsyncMock(return_value=SAMPLE_PROXYCURL_RESPONSE)):
            profile = await svc.fetch_by_url("https://linkedin.com/in/janedoe")
        assert profile.full_name == "Jane Doe"
        assert len(profile.work_experience) == 1

    @pytest.mark.asyncio
    async def test_fetch_by_url_raises_on_http_error(self, settings_with_key: Settings) -> None:
        svc = LinkedInService(settings_with_key)
        error = httpx.HTTPStatusError(
            "Unauthorized",
            request=httpx.Request("GET", "https://example.com"),
            response=httpx.Response(401),
        )
        with patch.object(svc, "_get", new=AsyncMock(side_effect=error)):
            with pytest.raises(httpx.HTTPStatusError):
                await svc.fetch_by_url("https://linkedin.com/in/janedoe")


# ---------------------------------------------------------------------------
# WebScraperService
# ---------------------------------------------------------------------------

SAMPLE_HTML = """
<html>
<body>
  <nav>Nav content to skip</nav>
  <main>
    <h1>Jane Doe</h1>
    <p>Senior Engineer at Acme Corp. Loves Python and distributed systems.</p>
  </main>
  <script>alert('skip me')</script>
  <footer>Footer to skip</footer>
</body>
</html>
"""


class TestExtractText:
    def test_removes_script_and_nav(self) -> None:
        text = _extract_text(SAMPLE_HTML)
        assert "alert" not in text
        assert "Nav content" not in text

    def test_keeps_main_content(self) -> None:
        text = _extract_text(SAMPLE_HTML)
        assert "Jane Doe" in text
        assert "Senior Engineer" in text

    def test_truncates_long_content(self) -> None:
        long_html = f"<p>{'x' * 10_000}</p>"
        text = _extract_text(long_html)
        assert len(text) <= 4000


class TestWebScraperService:
    @pytest.mark.asyncio
    async def test_scrape_returns_text(self, settings_no_key: Settings) -> None:
        svc = WebScraperService(settings_no_key)
        with patch.object(svc, "_fetch", new=AsyncMock(return_value=SAMPLE_HTML)):
            text = await svc.scrape("https://example.com/bio")
        assert "Jane Doe" in text

    @pytest.mark.asyncio
    async def test_scrape_returns_empty_on_http_error(self, settings_no_key: Settings) -> None:
        svc = WebScraperService(settings_no_key)
        error = httpx.HTTPStatusError(
            "Not Found",
            request=httpx.Request("GET", "https://example.com/missing"),
            response=httpx.Response(404),
        )
        with patch.object(svc, "_fetch", new=AsyncMock(side_effect=error)):
            text = await svc.scrape("https://example.com/missing")
        assert text == ""

    @pytest.mark.asyncio
    async def test_scrape_many(self, settings_no_key: Settings) -> None:
        svc = WebScraperService(settings_no_key)

        async def fake_fetch(url: str) -> str:
            return f"<p>Content of {url}</p>"

        with patch.object(svc, "_fetch", new=AsyncMock(side_effect=fake_fetch)):
            snippets = await svc.scrape_many(
                ["https://example.com/a", "https://example.com/b"]
            )
        assert len(snippets) == 2
        assert any("example.com/a" in s for s in snippets)
        assert any("example.com/b" in s for s in snippets)


# ---------------------------------------------------------------------------
# _merge_profiles
# ---------------------------------------------------------------------------

class TestMergeProfiles:
    def test_overlay_fills_empty_base(self) -> None:
        base = Profile()
        overlay = Profile(full_name="Jane Doe", headline="Engineer")
        merged = _merge_profiles(base, overlay)
        assert merged.full_name == "Jane Doe"
        assert merged.headline == "Engineer"

    def test_overlay_wins_on_conflict(self) -> None:
        base = Profile(full_name="Old Name")
        overlay = Profile(full_name="New Name")
        merged = _merge_profiles(base, overlay)
        assert merged.full_name == "New Name"

    def test_work_experience_deduplication(self) -> None:
        exp = WorkExperience(title="Engineer", company="Acme", source=ProfileSource.LINKEDIN)
        base = Profile(work_experience=[exp])
        overlay = Profile(work_experience=[exp])
        merged = _merge_profiles(base, overlay)
        assert len(merged.work_experience) == 1

    def test_skill_higher_endorsement_wins(self) -> None:
        base = Profile(skills=[Skill(name="Python", endorsements=5, source=ProfileSource.LINKEDIN)])
        overlay = Profile(skills=[Skill(name="Python", endorsements=50, source=ProfileSource.LINKEDIN)])
        merged = _merge_profiles(base, overlay)
        assert len(merged.skills) == 1
        assert merged.skills[0].endorsements == 50

    def test_sources_unioned(self) -> None:
        base = Profile(sources_used=[ProfileSource.LINKEDIN])
        overlay = Profile(sources_used=[ProfileSource.WEB])
        merged = _merge_profiles(base, overlay)
        assert ProfileSource.LINKEDIN in merged.sources_used
        assert ProfileSource.WEB in merged.sources_used

    def test_web_snippets_concatenated(self) -> None:
        base = Profile(raw_web_snippets=["snippet A"])
        overlay = Profile(raw_web_snippets=["snippet B"])
        merged = _merge_profiles(base, overlay)
        assert "snippet A" in merged.raw_web_snippets
        assert "snippet B" in merged.raw_web_snippets


# ---------------------------------------------------------------------------
# ProfileEnricher
# ---------------------------------------------------------------------------

class TestProfileEnricher:
    @pytest.mark.asyncio
    async def test_enrich_name_only_no_api_key(self, settings_no_key: Settings) -> None:
        enricher = ProfileEnricher(settings_no_key)
        request = ProfileRequest(full_name="Jane Doe")
        response = await enricher.enrich(request)
        assert response.profile.full_name == "Jane Doe"
        assert isinstance(response.errors, list)

    @pytest.mark.asyncio
    async def test_enrich_with_web_urls(self, settings_no_key: Settings) -> None:
        scraper = WebScraperService(settings_no_key)
        with patch.object(
            scraper, "_fetch", new=AsyncMock(return_value="<p>Jane Doe – Engineer</p>")
        ):
            enricher = ProfileEnricher(settings_no_key, web_scraper=scraper)
            request = ProfileRequest(
                full_name="Jane Doe",
                web_urls=["https://example.com/jane"],
            )
            response = await enricher.enrich(request)
        assert "web" in response.sources_used
        assert len(response.profile.raw_web_snippets) > 0

    @pytest.mark.asyncio
    async def test_enrich_linkedin_url_with_mock(self, settings_with_key: Settings) -> None:
        linkedin_svc = LinkedInService(settings_with_key)
        with patch.object(
            linkedin_svc, "_get", new=AsyncMock(return_value=SAMPLE_PROXYCURL_RESPONSE)
        ):
            enricher = ProfileEnricher(settings_with_key, linkedin_service=linkedin_svc)
            request = ProfileRequest(linkedin_url="https://linkedin.com/in/janedoe")
            response = await enricher.enrich(request)
        assert response.profile.full_name == "Jane Doe"
        assert "linkedin" in response.sources_used
        assert response.errors == []
