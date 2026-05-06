from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from starlette.concurrency import run_in_threadpool

from src.models.event_discovery import EventDiscoveryQuery, ExternalEventResult


class SerpApiGoogleEventsProvider:
    name = "serpapi"

    def __init__(self, api_key: str | None, timeout_s: int = 15) -> None:
        self._api_key = api_key
        self._timeout_s = timeout_s

    async def search(self, query: EventDiscoveryQuery) -> list[ExternalEventResult]:
        if not self._api_key:
            raise RuntimeError("SERPAPI_API_KEY is not set.")
        return await run_in_threadpool(self._search_sync, query)

    def _search_sync(self, query: EventDiscoveryQuery) -> list[ExternalEventResult]:
        params: dict[str, str] = {
            "engine": "google_events",
            "api_key": self._api_key,
        }
        if query.query:
            params["q"] = query.query
        if query.city:
            params["location"] = query.city
        # SerpApi supports multiple optional params; keep spike minimal.

        url = f"https://serpapi.com/search.json?{urlencode(params)}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "ai-profile-intelligience-event-discovery/1.0",
            },
        )
        with urlopen(request, timeout=self._timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))

        events = payload.get("events_results") or payload.get("events_result") or []
        if not isinstance(events, list):
            return []

        results: list[ExternalEventResult] = []
        for item in events:
            if not isinstance(item, dict):
                continue
            results.append(self._normalize_item(item, query))
        return results

    def _normalize_item(self, item: dict[str, Any], query: EventDiscoveryQuery) -> ExternalEventResult:
        title = str(item.get("title") or "").strip() or "Untitled event"
        link = item.get("link")
        external_url = str(link).strip() if link else None

        start_at: datetime | None = None
        end_at: datetime | None = None
        when = item.get("date")
        if isinstance(when, dict):
            start_at = _parse_dt(when.get("start_date"))
            end_at = _parse_dt(when.get("end_date"))
        elif isinstance(when, str):
            start_at = _parse_dt(when)

        address = None
        city = query.city
        location_name = None
        if isinstance(item.get("address"), list) and item["address"]:
            address = ", ".join(str(part) for part in item["address"] if part)
        if isinstance(item.get("venue"), dict):
            location_name = str(item["venue"].get("name") or "") or None

        is_free = None
        cost_label = None
        ticket_info = item.get("ticket_info")
        if isinstance(ticket_info, dict):
            cost_label = str(ticket_info.get("price") or "") or None
            if cost_label:
                is_free = "free" in cost_label.lower()

        relevance_reasons: list[str] = []
        if query.query:
            relevance_reasons.append(f'Matches "{query.query}"')
        if query.city:
            relevance_reasons.append(f"Near {query.city}")
        relevance_reasons.append("From serpapi")

        return ExternalEventResult(
            source="serpapi",
            external_id=str(item.get("event_id") or "") or None,
            external_url=external_url,
            title=title,
            description=str(item.get("description") or "") or None,
            location_name=location_name,
            address=address,
            city=city,
            start_at=start_at,
            end_at=end_at,
            timezone=None,
            cost_label=cost_label,
            is_free=is_free,
            image_url=str(item.get("thumbnail") or "") or None,
            category_labels=[],
            relevance_reasons=relevance_reasons,
        )


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    # Best-effort parsing for ISO-like inputs.
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

