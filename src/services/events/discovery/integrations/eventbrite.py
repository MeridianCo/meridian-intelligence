from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from starlette.concurrency import run_in_threadpool

from src.models.event_discovery import EventDiscoveryQuery, ExternalEventResult


class EventbriteProvider:
    name = "eventbrite"

    def __init__(self, private_token: str | None, timeout_s: int = 15) -> None:
        self._private_token = private_token
        self._timeout_s = timeout_s

    async def search(self, query: EventDiscoveryQuery) -> list[ExternalEventResult]:
        if not self._private_token:
            raise RuntimeError("EVENTBRITE_PRIVATE_TOKEN is not set.")
        return await run_in_threadpool(self._search_sync, query)

    def _search_sync(self, query: EventDiscoveryQuery) -> list[ExternalEventResult]:
        # Eventbrite shut down the public event search API (`/v3/events/search/`) in December 2019.
        # Without distribution partner access, Eventbrite does not offer a general-purpose
        # "events near me" public discovery endpoint via the API.
        #
        # This provider therefore only supports *organization-scoped* event listing:
        # - organizations the token owner belongs to, and/or
        # - organization IDs explicitly configured via env.
        org_ids = self._resolve_org_ids()
        if not org_ids:
            raise RuntimeError(
                "Eventbrite does not support public event discovery via API (the old `/v3/events/search/` was shut down). "
                "This integration only supports organization-scoped listings. "
                "Set EVENTBRITE_ORGANIZATION_IDS (comma-separated) to opt into listing specific organizers' events, "
                "or disable the provider via EVENT_DISCOVERY_ENABLE_EVENTBRITE=false."
            )

        results: list[ExternalEventResult] = []
        for org_id in org_ids:
            results.extend(self._list_events_for_org(org_id, query))
        return self._filter_results(results, query)

    def _resolve_org_ids(self) -> list[str]:
        import os

        configured = os.getenv("EVENTBRITE_ORGANIZATION_IDS", "").strip()
        if configured:
            return [part.strip() for part in configured.split(",") if part.strip()]

        # Fallback: fetch organizations for token owner.
        url = "https://www.eventbriteapi.com/v3/users/me/organizations/"
        payload = self._get_json(url)
        orgs = payload.get("organizations") or []
        if not isinstance(orgs, list):
            return []
        ids: list[str] = []
        for org in orgs:
            if isinstance(org, dict) and org.get("id"):
                ids.append(str(org["id"]))
        return ids

    def _list_events_for_org(self, org_id: str, query: EventDiscoveryQuery) -> list[ExternalEventResult]:
        params: dict[str, str] = {
            "page_size": str(min(max(query.limit or 20, 1), 50)),
        }
        if query.start_date:
            params["start_date.range_start"] = f"{query.start_date.isoformat()}T00:00:00Z"
        if query.end_date:
            params["start_date.range_end"] = f"{query.end_date.isoformat()}T23:59:59Z"

        url = f"https://www.eventbriteapi.com/v3/organizations/{org_id}/events/"
        if params:
            url = f"{url}?{urlencode(params)}"
        payload = self._get_json(url)

        items = payload.get("events") or []
        if not isinstance(items, list):
            return []

        results: list[ExternalEventResult] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            results.append(self._normalize_item(item, query))
        return results

    def _get_json(self, url: str) -> dict[str, Any]:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._private_token}",
                "User-Agent": "ai-profile-intelligience-event-discovery/1.0",
            },
        )
        try:
            with urlopen(request, timeout=self._timeout_s) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except HTTPError as exc:
            raise RuntimeError(f"Eventbrite request failed ({exc.code}). Requested URL: {url}") from exc

    def _filter_results(
        self, results: list[ExternalEventResult], query: EventDiscoveryQuery
    ) -> list[ExternalEventResult]:
        filtered = results
        if query.query:
            needle = query.query.strip().lower()

            def matches(event: ExternalEventResult) -> bool:
                if needle in event.title.lower():
                    return True
                if event.description and needle in event.description.lower():
                    return True
                return False

            filtered = [event for event in filtered if matches(event)]
        if query.limit and len(filtered) > query.limit:
            filtered = filtered[: query.limit]
        return filtered

    def _normalize_item(self, item: dict[str, Any], query: EventDiscoveryQuery) -> ExternalEventResult:
        name = item.get("name") if isinstance(item.get("name"), dict) else {}
        title = str(name.get("text") or "").strip() if isinstance(name, dict) else ""
        title = title or "Untitled event"

        description = None
        desc = item.get("description")
        if isinstance(desc, dict):
            description = str(desc.get("text") or "") or None

        external_url = str(item.get("url") or "") or None
        event_id = str(item.get("id") or "") or None

        start_at = None
        end_at = None
        timezone = None
        start = item.get("start")
        if isinstance(start, dict):
            start_at = _parse_dt(start.get("utc") or start.get("local"))
            timezone = str(start.get("timezone") or "") or None
        end = item.get("end")
        if isinstance(end, dict):
            end_at = _parse_dt(end.get("utc") or end.get("local"))

        image_url = None
        logo = item.get("logo")
        if isinstance(logo, dict):
            image_url = str(logo.get("url") or "") or None

        relevance_reasons: list[str] = []
        if query.query:
            relevance_reasons.append(f'Matches "{query.query}"')
        if query.city:
            relevance_reasons.append(f"Near {query.city}")
        relevance_reasons.append("From eventbrite")

        return ExternalEventResult(
            source="eventbrite",
            external_id=event_id,
            external_url=external_url,
            title=title,
            description=description,
            location_name=None,
            address=None,
            city=query.city,
            latitude=None,
            longitude=None,
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
