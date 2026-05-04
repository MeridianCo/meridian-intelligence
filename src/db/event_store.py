"""SQLite persistence for discovered events."""

from __future__ import annotations

from pathlib import Path
import json
import sqlite3

from src.services.shared.scrapers.event_builder import EventCandidate, candidate_to_dict


DEFAULT_EVENT_DB = Path("data/events.sqlite3")


def save_event_candidates(
    candidates: list[EventCandidate],
    db_path: str | Path = DEFAULT_EVENT_DB,
) -> list[dict[str, object]]:
    """Upsert event candidates by stable fingerprint."""

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        _ensure_schema(connection)
        saved = [_upsert_candidate(connection, candidate) for candidate in candidates]
        connection.commit()
    finally:
        connection.close()
    return saved


def list_saved_events(db_path: str | Path = DEFAULT_EVENT_DB) -> list[dict[str, object]]:
    """Return saved events as JSON-friendly dictionaries."""

    path = Path(db_path)
    if not path.exists():
        return []
    connection = sqlite3.connect(path)
    try:
        connection.row_factory = sqlite3.Row
        _ensure_schema(connection)
        rows = connection.execute(
            "SELECT payload FROM events ORDER BY score DESC, updated_at DESC"
        ).fetchall()
    finally:
        connection.close()
    return [json.loads(row["payload"]) for row in rows]


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            fingerprint TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            payload TEXT NOT NULL,
            score INTEGER NOT NULL,
            duplicate_count INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _upsert_candidate(connection: sqlite3.Connection, candidate: EventCandidate) -> dict[str, object]:
    payload = candidate_to_dict(candidate)
    fingerprint = str(payload["fingerprint"])
    existing = connection.execute(
        "SELECT payload FROM events WHERE fingerprint = ?",
        (fingerprint,),
    ).fetchone()
    if existing:
        payload = _merge_payloads(json.loads(existing[0]), payload)

    connection.execute(
        """
        INSERT INTO events (fingerprint, title, payload, score, duplicate_count)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(fingerprint) DO UPDATE SET
            title = excluded.title,
            payload = excluded.payload,
            score = excluded.score,
            duplicate_count = excluded.duplicate_count,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            fingerprint,
            payload["title"],
            json.dumps(payload, sort_keys=True),
            payload["score"],
            payload["duplicate_count"],
        ),
    )
    return payload


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
    for key in ["description", "location", "venue", "organizer"]:
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
