from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from starlette.concurrency import run_in_threadpool

from src.models.event_discovery import EventDiscoveryQuery, ExternalEventResult


class TicketmasterDiscoveryProvider:
    name = "ticketmaster"

    def __init__(self, api_key: str | None, timeout_s: int = 15) -> None:
        self._api_key = api_key
        self._timeout_s = timeout_s

    async def search(self, query: EventDiscoveryQuery) -> list[ExternalEventResult]:
        if not self._api_key:
            raise RuntimeError("TICKETMASTER_API_KEY is not set.")
        return await run_in_threadpool(self._search_sync, query)

    def _search_sync(self, query: EventDiscoveryQuery) -> list[ExternalEventResult]:
        params: dict[str, str] = {
            "apikey": self._api_key,
            "size": str(min(max(query.limit or 20, 1), 200)),
        }
        if query.query:
            params["keyword"] = query.query
        # Location strategy:
        # - Prefer lat/long + radius when provided (better for "near me").
        # - Otherwise fall back to city text match.
        if query.latitude is not None and query.longitude is not None:
            params["latlong"] = f"{query.latitude},{query.longitude}"
            params["radius"] = str(query.radius_km)
            params["unit"] = "km"
        elif query.city:
            params["city"] = query.city
        if query.start_date:
            params["startDateTime"] = f"{query.start_date.isoformat()}T00:00:00Z"
        if query.end_date:
            params["endDateTime"] = f"{query.end_date.isoformat()}T23:59:59Z"

        url = f"https://app.ticketmaster.com/discovery/v2/events.json?{urlencode(params)}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "ai-profile-intelligience-event-discovery/1.0",
            },
        )
        with urlopen(request, timeout=self._timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))

        embedded = payload.get("_embedded") or {}
        items = embedded.get("events") or []
        if not isinstance(items, list):
            return []

        results: list[ExternalEventResult] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            results.append(self._normalize_item(item, query))
        return results

    def _normalize_item(self, item: dict[str, Any], query: EventDiscoveryQuery) -> ExternalEventResult:
        title = str(item.get("name") or "").strip() or "Untitled event"
        external_url = str(item.get("url") or "") or None

        start_at = None
        end_at = None
        timezone = None
        dates = item.get("dates") or {}
        start = dates.get("start") if isinstance(dates, dict) else {}
        if isinstance(start, dict):
            start_at = _parse_dt(start.get("dateTime"))
            timezone = str(start.get("timeZone") or "") or None

        venue = None
        city = None
        address = None
        latitude = None
        longitude = None
        embedded = item.get("_embedded") or {}
        venues = embedded.get("venues") if isinstance(embedded, dict) else None
        if isinstance(venues, list) and venues:
            venue0 = venues[0]
            if isinstance(venue0, dict):
                venue = str(venue0.get("name") or "") or None
                city_obj = venue0.get("city")
                if isinstance(city_obj, dict):
                    city = str(city_obj.get("name") or "") or None
                addr_obj = venue0.get("address")
                if isinstance(addr_obj, dict):
                    address = str(addr_obj.get("line1") or "") or None
                loc_obj = venue0.get("location")
                if isinstance(loc_obj, dict):
                    latitude = _parse_float(loc_obj.get("latitude"))
                    longitude = _parse_float(loc_obj.get("longitude"))

        image_url = None
        images = item.get("images")
        if isinstance(images, list) and images:
            best = max(
                (img for img in images if isinstance(img, dict)),
                key=lambda img: int(img.get("width") or 0) * int(img.get("height") or 0),
                default=None,
            )
            if best:
                image_url = str(best.get("url") or "") or None

        relevance_reasons: list[str] = []
        if query.query:
            relevance_reasons.append(f'Matches "{query.query}"')
        if query.city:
            relevance_reasons.append(f"Near {query.city}")
        relevance_reasons.append("From ticketmaster")

        return ExternalEventResult(
            source="ticketmaster",
            external_id=str(item.get("id") or "") or None,
            external_url=external_url,
            title=title,
            description=None,
            location_name=venue,
            address=address,
            city=city or query.city,
            latitude=latitude,
            longitude=longitude,
            start_at=start_at,
            end_at=end_at,
            timezone=timezone,
            cost_label=None,
            is_free=None,
            image_url=image_url,
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
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
