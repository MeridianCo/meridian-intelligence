"""Blog scraper for local event discovery.

The scraper intentionally uses the Python standard library so it can run in
small deployments without browser drivers or paid event APIs. It is tuned for
blogs and local listings: fetch HTML, extract readable text plus links, detect
date-bearing snippets, then score them against the requested city and interests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import re


MONTH_PATTERN = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?"
)
DATE_PATTERN = re.compile(
    rf"\b(?:{MONTH_PATTERN})\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,\s+\d{{4}})?\b"
    r"|\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
    re.IGNORECASE,
)
EVENT_WORDS = re.compile(
    r"\b(event|workshop|meetup|conference|festival|show|class|clinic|"
    r"webinar|networking|panel|summit|market|concert)\b",
    re.IGNORECASE,
)


@dataclass
class BlogSource:
    """A source URL and optional label for local event blog scraping."""

    url: str
    name: str | None = None


@dataclass
class EventSearch:
    """Search preferences for discovering nearby relevant events."""

    city: str
    interests: list[str] = field(default_factory=list)
    nearby_locations: list[str] = field(default_factory=list)
    sources: list[BlogSource] = field(default_factory=list)
    max_results: int = 10


@dataclass
class EventCandidate:
    """A scored event-like snippet discovered from a blog page."""

    title: str
    source_url: str
    event_url: str
    snippet: str
    score: int
    dates: list[str] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)


class BlogTextParser(HTMLParser):
    """Extract title, links, and visible text from ordinary blog HTML."""

    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.title = ""
        self.links: list[tuple[str, str]] = []
        self._current_link: str | None = None
        self._current_link_text: list[str] = []
        self._in_title = False
        self._skip_depth = 0
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "a" and attrs_dict.get("href"):
            self._current_link = urljoin(self.base_url, attrs_dict["href"] or "")
            self._current_link_text = []
        if tag in {"p", "br", "li", "h1", "h2", "h3", "article", "section"}:
            self._text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._current_link:
            link_text = " ".join(" ".join(self._current_link_text).split())
            self.links.append((link_text, self._current_link))
            self._current_link = None
            self._current_link_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
        if self._current_link is not None:
            self._current_link_text.append(text)
        self._text_parts.append(text)

    @property
    def text(self) -> str:
        return "\n".join(part for part in self._text_parts if part.strip())


def scrape_matching_events(search: EventSearch) -> list[EventCandidate]:
    """Fetch configured blogs and return event candidates sorted by relevance."""

    candidates: list[EventCandidate] = []
    for source in search.sources:
        html = fetch_url(source.url)
        parser = BlogTextParser(source.url)
        parser.feed(html)
        candidates.extend(_extract_candidates(search, source, parser))

    return _dedupe_candidates(candidates)[: search.max_results]


def fetch_url(url: str, timeout: int = 10) -> str:
    """Fetch a blog page with a friendly user agent."""

    request = Request(
        url,
        headers={
            "User-Agent": "ai-profile-intelligience-event-scraper/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _extract_candidates(
    search: EventSearch,
    source: BlogSource,
    parser: BlogTextParser,
) -> list[EventCandidate]:
    snippets = _date_snippets(parser.text)
    link_lookup = _relevant_links(parser.links)
    candidates: list[EventCandidate] = []

    for snippet in snippets:
        title = _title_from_snippet(snippet, parser.title, link_lookup.keys())
        event_url = _best_link_for_snippet(snippet, source.url, link_lookup)
        dates = sorted(set(match.group(0) for match in DATE_PATTERN.finditer(snippet)))
        score, matched_terms = _score_snippet(search, snippet, title)
        if score <= 0:
            continue
        candidates.append(
            EventCandidate(
                title=title,
                source_url=source.url,
                event_url=event_url,
                snippet=snippet,
                score=score,
                dates=dates,
                matched_terms=matched_terms,
            )
        )

    return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)


def _date_snippets(text: str) -> list[str]:
    normalized = re.sub(r"[ \t]+", " ", text)
    paragraphs = [part.strip() for part in re.split(r"\n+", normalized) if part.strip()]
    snippets: list[str] = []

    for index, paragraph in enumerate(paragraphs):
        if not DATE_PATTERN.search(paragraph):
            continue
        neighbors = paragraphs[max(0, index - 1) : index + 2]
        snippet = " ".join(neighbors)
        snippets.append(snippet[:700])

    return snippets


def _relevant_links(links: Iterable[tuple[str, str]]) -> dict[str, str]:
    relevant: dict[str, str] = {}
    for text, url in links:
        if not text:
            continue
        if EVENT_WORDS.search(text) or DATE_PATTERN.search(text) or 3 <= len(text.split()) <= 12:
            relevant[text] = url
    return relevant


def _score_snippet(search: EventSearch, snippet: str, title: str) -> tuple[int, list[str]]:
    haystack = f"{title} {snippet}".lower()
    matched_terms: list[str] = []
    score = 0

    for term, weight in [(search.city, 4), *[(nearby, 2) for nearby in search.nearby_locations]]:
        if term and term.lower() in haystack:
            score += weight
            matched_terms.append(term)

    for interest in search.interests:
        if interest and interest.lower() in haystack:
            score += 3
            matched_terms.append(interest)

    if EVENT_WORDS.search(haystack):
        score += 2
    if DATE_PATTERN.search(haystack):
        score += 1

    return score, matched_terms


def _title_from_snippet(snippet: str, page_title: str, link_texts: Iterable[str]) -> str:
    for link_text in link_texts:
        if link_text and link_text in snippet:
            return link_text[:120]

    first_sentence = re.split(r"(?<=[.!?])\s+", snippet.strip())[0]
    if 8 <= len(first_sentence) <= 120:
        return first_sentence
    if page_title:
        return page_title[:120]
    return snippet[:120]


def _best_link_for_snippet(snippet: str, fallback_url: str, links: dict[str, str]) -> str:
    for link_text, url in links.items():
        if link_text in snippet:
            return url
    return fallback_url


def _dedupe_candidates(candidates: list[EventCandidate]) -> list[EventCandidate]:
    deduped: dict[tuple[str, str], EventCandidate] = {}
    for candidate in candidates:
        key = (candidate.event_url, " ".join(candidate.dates))
        existing = deduped.get(key)
        if existing is None or candidate.score > existing.score:
            deduped[key] = candidate

    return sorted(deduped.values(), key=lambda candidate: candidate.score, reverse=True)


def candidate_to_dict(candidate: EventCandidate) -> dict[str, object]:
    """Convert an event candidate into JSON-friendly output."""

    return {
        "title": candidate.title,
        "source_url": candidate.source_url,
        "event_url": candidate.event_url,
        "snippet": candidate.snippet,
        "score": candidate.score,
        "dates": candidate.dates,
        "matched_terms": candidate.matched_terms,
        "scraped_at": date.today().isoformat(),
    }
