"""Supabase persistence for discovered events."""

from __future__ import annotations

from typing import Any

from src.services.events.scrape.event_scraping import EventCandidate, candidate_to_dict

EVENTS_TABLE = "scraped_events"

def save_event_candidates(
    candidates: list[EventCandidate],
    supabase_client: Any | None = None,
) -> list[dict[str, object]]:
    """Upsert event candidates into Supabase by stable fingerprint."""

    client = supabase_client or _default_supabase_client()
    payloads = [_payload_for_supabase(candidate) for candidate in candidates]
    if not payloads:
        return []
    existing = _existing_payloads(client, [str(payload["fingerprint"]) for payload in payloads])
    for payload in payloads:
        fingerprint = str(payload["fingerprint"])
        if fingerprint in existing:
            merged_payload = _merge_payloads(existing[fingerprint], dict(payload["payload"]))
            payload["payload"] = merged_payload
            payload["score"] = merged_payload["score"]
            payload["duplicate_count"] = merged_payload["duplicate_count"]
    client.table(EVENTS_TABLE).upsert(payloads, on_conflict="fingerprint").execute()
    return [payload["payload"] for payload in payloads]


def list_saved_events(supabase_client: Any | None = None) -> list[dict[str, object]]:
    """Return saved event payloads from Supabase."""

    client = supabase_client or _default_supabase_client()
    result = (
        client.table(EVENTS_TABLE)
        .select("payload")
        .order("score", desc=True)
        .execute()
    )
    return [row.get("payload", {}) for row in result.data or []]


def search_saved_events(
    *,
    query: str | None = None,
    city: str | None = None,
    limit: int = 20,
    supabase_client: Any | None = None,
) -> list[dict[str, object]]:
    """Search saved scraped event payloads for UI/API discovery flows."""

    client = supabase_client or _default_supabase_client()
    request = client.table(EVENTS_TABLE).select("payload,title,city,score")
    clean_query = (query or "").strip()
    clean_city = (city or "").strip()
    if clean_query:
        request = request.ilike("search_text", f"%{clean_query}%")
    if clean_city:
        request = request.eq("city", clean_city)
    result = request.order("score", desc=True).limit(limit).execute()
    return [row.get("payload", {}) for row in result.data or []]


def _default_supabase_client() -> Any:
    from src.db import supabase

    if supabase is None:
        raise RuntimeError(
            "Supabase client is not configured. Install supabase and set SUPABASE_URL "
            "and SUPABASE_SERVICE_ROLE_KEY."
        )
    return supabase


def _payload_for_supabase(candidate: EventCandidate) -> dict[str, object]:
    payload = candidate_to_dict(candidate)
    fingerprint = str(payload["fingerprint"])
    return {
        "fingerprint": fingerprint,
        "title": payload["title"],
        "city": _city_for_payload(payload),
        "event_url": payload.get("event_url"),
        "source_url": payload.get("source_url"),
        "payload": payload,
        "score": payload["score"],
        "duplicate_count": payload["duplicate_count"],
        "search_text": _search_text_for_payload(payload),
    }


def _city_for_payload(payload: dict[str, object]) -> str | None:
    details = payload.get("details")
    if isinstance(details, dict):
        location = details.get("location")
        if location:
            return str(location).split(",")[0].strip()
    return None


def _search_text_for_payload(payload: dict[str, object]) -> str:
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    values = [
        payload.get("title"),
        payload.get("snippet"),
        payload.get("event_url"),
        payload.get("source_url"),
        *(payload.get("matched_terms") or []),
        details.get("description") if isinstance(details, dict) else None,
        details.get("location") if isinstance(details, dict) else None,
        details.get("venue") if isinstance(details, dict) else None,
        details.get("organizer") if isinstance(details, dict) else None,
    ]
    return " ".join(str(value) for value in values if value).lower()


def _existing_payloads(client: Any, fingerprints: list[str]) -> dict[str, dict[str, object]]:
    if not fingerprints:
        return {}
    result = (
        client.table(EVENTS_TABLE)
        .select("fingerprint,payload")
        .in_("fingerprint", fingerprints)
        .execute()
    )
    return {
        str(row["fingerprint"]): dict(row.get("payload", {}))
        for row in result.data or []
        if row.get("fingerprint")
    }


def _merge_payloads(existing: dict[str, object], incoming: dict[str, object]) -> dict[str, object]:
    merged = dict(existing)
    for key in ["source_urls", "event_urls", "dates", "matched_terms"]:
        merged[key] = _append_unique(
            list(existing.get(key, [])),
            list(incoming.get(key, [])),
        )
    merged["score"] = max(int(existing.get("score", 0)), int(incoming.get("score", 0)))
    merged["duplicate_count"] = max(
        int(existing.get("duplicate_count", 1)),
        int(incoming.get("duplicate_count", 1)),
    )
    if len(str(incoming.get("snippet", ""))) > len(str(existing.get("snippet", ""))):
        merged["snippet"] = incoming["snippet"]
    merged["details"] = _merge_details(
        dict(existing.get("details", {})),
        dict(incoming.get("details", {})),
    )
    return merged


def _merge_details(existing: dict[str, object], incoming: dict[str, object]) -> dict[str, object]:
    merged = dict(existing)
    for key in [
        "description",
        "location",
        "venue",
        "organizer",
        "start_date",
        "end_date",
        "image_url",
        "ticket_url",
    ]:
        if not merged.get(key) and incoming.get(key):
            merged[key] = incoming[key]
        if key == "description" and len(str(incoming.get(key, ""))) > len(str(merged.get(key, ""))):
            merged[key] = incoming[key]
    for key in ["times", "prices"]:
        merged[key] = _append_unique(
            list(existing.get(key, [])),
            list(incoming.get(key, [])),
        )
    return merged


def _append_unique(existing: list[str], new_values: list[str]) -> list[str]:
    merged = list(existing)
    for value in new_values:
        if value and value not in merged:
            merged.append(value)
    return merged
