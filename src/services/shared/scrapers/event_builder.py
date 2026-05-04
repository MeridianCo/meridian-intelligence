"""Blog scraper for local event discovery.

The scraper intentionally uses the Python standard library so it can run in
small deployments without browser drivers or paid event APIs. It is tuned for
blogs and local listings: fetch HTML, extract readable text plus links, detect
date-bearing snippets, then score them against the requested city and interests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import re
import unicodedata


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
TIME_PATTERN = re.compile(
    r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)\b",
    re.IGNORECASE,
)
PRICE_PATTERN = re.compile(
    r"\b(?:free|\$\d+(?:\.\d{2})?|tickets?\s+(?:from|start(?:ing)? at)\s+\$\d+(?:\.\d{2})?)\b",
    re.IGNORECASE,
)
VENUE_PATTERN = re.compile(
    r"\b(?:at|venue:|location:)\s+([A-Z][A-Za-z0-9&'. -]{2,80})",
    re.IGNORECASE,
)
ORGANIZER_PATTERN = re.compile(
    r"\b(?:hosted by|presented by|organized by|organised by)\s+([A-Z][A-Za-z0-9&'. -]{2,80})",
    re.IGNORECASE,
)
EVENT_WORDS = re.compile(
    r"\b(event|workshop|meetup|conference|festival|show|class|clinic|"
    r"webinar|networking|panel|summit|market|concert)\b",
    re.IGNORECASE,
)
SOURCE_WORDS = re.compile(
    r"\b(event|events|calendar|things to do|what'?s on|happening|"
    r"meetup|workshop|conference|festival|community|blog)\b",
    re.IGNORECASE,
)


@dataclass
class EventDetails:
    """Structured details gathered from the event snippet itself."""

    description: str = ""
    location: str | None = None
    venue: str | None = None
    times: list[str] = field(default_factory=list)
    prices: list[str] = field(default_factory=list)
    organizer: str | None = None


@dataclass
class BlogSource:
    """A source URL and optional label for local event blog scraping."""

    url: str
    name: str | None = None
    discovery_score: int = 0


@dataclass
class EventSearch:
    """Search preferences for discovering nearby relevant events."""

    city: str
    interests: list[str] = field(default_factory=list)
    nearby_locations: list[str] = field(default_factory=list)
    sources: list[BlogSource] = field(default_factory=list)
    seed_urls: list[str] = field(default_factory=list)
    max_results: int = 10
    max_discovered_sources: int = 5


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
    source_urls: list[str] = field(default_factory=list)
    event_urls: list[str] = field(default_factory=list)
    duplicate_count: int = 1
    details: EventDetails = field(default_factory=EventDetails)
    fingerprint: str = ""


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
    sources = _append_sources(
        search.sources,
        discover_event_sources(search)[: search.max_discovered_sources],
    )
    for source in sources:
        html = fetch_url(source.url)
        parser = BlogTextParser(source.url)
        parser.feed(html)
        candidates.extend(_extract_candidates(search, source, parser))

    return _dedupe_candidates(candidates)[: search.max_results]


def discover_event_sources(search: EventSearch) -> list[BlogSource]:
    """Discover likely event/listing pages from user-provided seed URLs."""

    discovered: dict[str, BlogSource] = {}
    for seed_url in search.seed_urls:
        html = fetch_url(seed_url)
        parser = BlogTextParser(seed_url)
        parser.feed(html)
        for text, url in parser.links:
            if not _same_site(seed_url, url):
                continue
            score = _score_source_link(search, text, url)
            if score <= 0:
                continue
            existing = discovered.get(url)
            if existing is None or score > existing.discovery_score:
                discovered[url] = BlogSource(url=url, name=text or None, discovery_score=score)

    return sorted(discovered.values(), key=lambda source: source.discovery_score, reverse=True)


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


def _score_source_link(search: EventSearch, text: str, url: str) -> int:
    haystack = f"{text} {url}".lower()
    score = 0
    if SOURCE_WORDS.search(haystack):
        score += 3
    if search.city.lower() in haystack:
        score += 2
    for interest in search.interests:
        if interest.lower() in haystack:
            score += 2
    for nearby in search.nearby_locations:
        if nearby.lower() in haystack:
            score += 1
    return score


def _same_site(seed_url: str, candidate_url: str) -> bool:
    seed_host = urlparse(seed_url).netloc.lower().removeprefix("www.")
    candidate_host = urlparse(candidate_url).netloc.lower().removeprefix("www.")
    return bool(seed_host and candidate_host and seed_host == candidate_host)


def _append_sources(existing: list[BlogSource], discovered: list[BlogSource]) -> list[BlogSource]:
    sources_by_url = {source.url: source for source in existing}
    for source in discovered:
        sources_by_url.setdefault(source.url, source)
    return list(sources_by_url.values())


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
        details = _extract_event_details(search, snippet)
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
                source_urls=[source.url],
                event_urls=[event_url],
                details=details,
                fingerprint=event_fingerprint(title, dates, details.location),
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
        neighbors = paragraphs[max(0, index - 1) : index + 3]
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


def _extract_event_details(search: EventSearch, snippet: str) -> EventDetails:
    description = _clean_description(snippet)
    venue = _first_group(VENUE_PATTERN, snippet)
    organizer = _first_group(ORGANIZER_PATTERN, snippet)
    location = _best_location(search, snippet, venue)

    return EventDetails(
        description=description,
        location=location,
        venue=venue,
        times=_unique_matches(TIME_PATTERN, snippet),
        prices=_unique_matches(PRICE_PATTERN, snippet),
        organizer=organizer,
    )


def _clean_description(snippet: str) -> str:
    cleaned = re.sub(r"\s+", " ", snippet).strip()
    return cleaned[:500]


def _first_group(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    value = re.split(r"[.;\n]", match.group(1))[0].strip()
    return value or None


def _best_location(search: EventSearch, snippet: str, venue: str | None) -> str | None:
    for location in [search.city, *search.nearby_locations]:
        if location and re.search(rf"\b{re.escape(location)}\b", snippet, re.IGNORECASE):
            return location
    return venue


def _unique_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    values: list[str] = []
    for match in pattern.finditer(text):
        value = match.group(0).strip()
        if value and value not in values:
            values.append(value)
    return values


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
        if not candidate.fingerprint:
            candidate.fingerprint = event_fingerprint(candidate.title, candidate.dates, candidate.details.location)
        key = (candidate.fingerprint, "")
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = candidate
            continue

        _merge_duplicate(existing, candidate)
        if candidate.score > existing.score:
            existing.title = candidate.title
            existing.source_url = candidate.source_url
            existing.event_url = candidate.event_url
            existing.snippet = candidate.snippet
            existing.score = candidate.score

    return sorted(deduped.values(), key=lambda candidate: candidate.score, reverse=True)


def _normalize_event_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    normalized = re.sub(r"\b(the|a|an|event|workshop|meetup|conference)\b", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized.lower())
    return " ".join(normalized.split())


def event_fingerprint(title: str, dates: list[str], location: str | None = None) -> str:
    """Stable key used to merge the same event across sources and scrape runs."""

    parts = [_normalize_event_title(title), _primary_date(dates)]
    if location:
        parts.append(_normalize_event_title(location))
    return "|".join(part for part in parts if part)


def _primary_date(dates: list[str]) -> str:
    if not dates:
        return ""
    return dates[0].lower().replace(",", "")


def _merge_duplicate(existing: EventCandidate, duplicate: EventCandidate) -> None:
    existing.duplicate_count += duplicate.duplicate_count
    existing.source_urls = _append_unique(existing.source_urls, duplicate.source_urls or [duplicate.source_url])
    existing.event_urls = _append_unique(existing.event_urls, duplicate.event_urls or [duplicate.event_url])
    existing.dates = _append_unique(existing.dates, duplicate.dates)
    existing.matched_terms = _append_unique(existing.matched_terms, duplicate.matched_terms)
    existing.score = max(existing.score, duplicate.score) + 1
    existing.details = _merge_details(existing.details, duplicate.details)
    if duplicate.snippet not in existing.snippet:
        existing.snippet = f"{existing.snippet} {duplicate.snippet}"[:1000]


def _merge_details(existing: EventDetails, duplicate: EventDetails) -> EventDetails:
    return EventDetails(
        description=existing.description if len(existing.description) >= len(duplicate.description) else duplicate.description,
        location=existing.location or duplicate.location,
        venue=existing.venue or duplicate.venue,
        times=_append_unique(existing.times, duplicate.times),
        prices=_append_unique(existing.prices, duplicate.prices),
        organizer=existing.organizer or duplicate.organizer,
    )


def _append_unique(existing: list[str], new_values: list[str]) -> list[str]:
    merged = list(existing)
    for value in new_values:
        if value and value not in merged:
            merged.append(value)
    return merged


def candidate_to_dict(candidate: EventCandidate) -> dict[str, object]:
    """Convert an event candidate into JSON-friendly output."""

    return {
        "title": candidate.title,
        "source_url": candidate.source_url,
        "event_url": candidate.event_url,
        "source_urls": candidate.source_urls or [candidate.source_url],
        "event_urls": candidate.event_urls or [candidate.event_url],
        "duplicate_count": candidate.duplicate_count,
        "fingerprint": candidate.fingerprint or event_fingerprint(
            candidate.title,
            candidate.dates,
            candidate.details.location,
        ),
        "snippet": candidate.snippet,
        "details": {
            "description": candidate.details.description,
            "location": candidate.details.location,
            "venue": candidate.details.venue,
            "times": candidate.details.times,
            "prices": candidate.details.prices,
            "organizer": candidate.details.organizer,
        },
        "score": candidate.score,
        "dates": candidate.dates,
        "matched_terms": candidate.matched_terms,
        "scraped_at": date.today().isoformat(),
    }
