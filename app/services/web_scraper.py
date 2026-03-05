"""Web scraping service for public profile pages.

Fetches arbitrary URLs and extracts plain-text snippets that the enricher can
use to supplement structured LinkedIn data.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Settings

logger = logging.getLogger(__name__)

# Tags that are unlikely to contain useful profile text
_SKIP_TAGS = {
    "script", "style", "noscript", "nav", "footer", "header",
    "aside", "form", "button", "input", "select",
}

# Maximum characters to keep per page to stay within reasonable token budgets
_MAX_SNIPPET_CHARS = 4000


def _extract_text(html: str) -> str:
    """Return clean, deduplicated plain text from an HTML document."""
    soup = BeautifulSoup(html, "lxml")

    # Remove noisy elements
    for tag in soup.find_all(_SKIP_TAGS):
        tag.decompose()

    raw = soup.get_text(separator=" ", strip=True)
    # Collapse excessive whitespace
    text = re.sub(r"\s{2,}", " ", raw)
    return text[:_MAX_SNIPPET_CHARS]


class WebScraperService:
    """Fetches and parses public web pages to extract profile-relevant text."""

    # Browsers reject scraping; a neutral UA is enough for most public pages.
    _DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; ai-profile-intelligence/0.1; "
            "+https://github.com/MeridianCo/ai-profile-intelligience)"
        )
    }

    def __init__(self, settings: Settings, client: Optional[httpx.AsyncClient] = None) -> None:
        self._settings = settings
        self._client = client  # injected for testing

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
    )
    async def _fetch(self, url: str) -> str:
        if self._client:
            response = await self._client.get(
                url, headers=self._DEFAULT_HEADERS, follow_redirects=True
            )
        else:
            async with httpx.AsyncClient(
                timeout=self._settings.http_timeout, follow_redirects=True
            ) as client:
                response = await client.get(url, headers=self._DEFAULT_HEADERS)
        response.raise_for_status()
        return response.text

    async def scrape(self, url: str) -> str:
        """Return a plain-text snippet from ``url``, or an empty string on error."""
        try:
            html = await self._fetch(url)
            return _extract_text(html)
        except httpx.HTTPStatusError as exc:
            logger.warning("HTTP %s when scraping %s", exc.response.status_code, url)
            return ""
        except httpx.RequestError as exc:
            logger.warning("Network error scraping %s: %s", url, exc)
            return ""

    async def scrape_many(self, urls: list[str]) -> list[str]:
        """Scrape multiple URLs and return a list of non-empty snippets."""
        import asyncio

        results = await asyncio.gather(*(self.scrape(u) for u in urls))
        return [r for r in results if r]
