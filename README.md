# ai-profile-intelligience
Consolidate information about a profile from multiple sources (primarily LinkedIn) so the rest of the system has structured context.

Run the API:

```bash
uvicorn src.api.main:app --reload
```

or 

```bash
python (or python3) -m src.api.main

## Event blog scraper

The event discovery service scrapes blog or local listing pages and ranks date-bearing event snippets by city, nearby locations, and interests.

Scraper implementation: `src/services/shared/scrapers/event_scraper.py`

Search for matching events:

```bash
curl -X POST http://localhost:8000/events/scrape/search \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Calgary",
    "nearby_locations": ["Airdrie", "Cochrane"],
    "interests": ["AI", "healthcare", "founders"],
    "source_urls": ["https://example.com/local-events-blog"],
    "seed_urls": ["https://example.com"],
    "discover_sources": true,
    "persist_results": true,
    "max_results": 10
  }'
```

The scraper can discover likely event source pages from seed URLs, extract `schema.org/Event` JSON-LD when available, persist merged events to Supabase, and score source reliability. Supabase persistence expects an `events` table keyed by `fingerprint`, with columns for `title`, `payload`, `score`, and `duplicate_count`.

The response includes discovered sources, source reliability, each candidate's title, source URL, event URL, stable fingerprint, all duplicate source/event URLs, duplicate count, snippet, detected dates, matched terms, relevance score, and gathered event details such as description, location, venue, times, prices, organizer, image URL, ticket URL, and structured start/end dates.

## Event discovery (API providers)

This repo also exposes an API-backed event discovery endpoint that queries external providers and returns normalized results.

Environment variables are listed in `.env.example` (provider keys must remain server-side).

Search (GET):

```bash
curl "http://localhost:8000/event-discovery/search?query=networking&city=Calgary&limit=10"
```

Required: provide `query` plus either `city` or both `latitude` + `longitude`. If you omit dates, the API defaults to a 30-day window starting today.

Search (POST):

```bash
curl -X POST http://localhost:8000/events/discovery/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "networking",
    "city": "Calgary",
    "start_date": "2026-06-01",
    "end_date": "2026-06-30",
    "limit": 10
  }'
```

If a provider fails (missing key, auth, quota), the endpoint still returns results from other providers and includes a `provider_errors` map in the response.

### Eventbrite note

Eventbrite shut down their public `GET /v3/events/search/` endpoint in December 2019. This code uses organization-based APIs instead:

- `GET /v3/users/me/organizations/` to discover organization IDs for the token owner
- `GET /v3/organizations/:organization_id/events/` to list events

You can optionally set `EVENTBRITE_ORGANIZATION_IDS` in your `.env` to explicitly control which organizations are queried.

Because this is not public “events near me” discovery, the Eventbrite provider is disabled by default (`EVENT_DISCOVERY_ENABLE_EVENTBRITE=false`).
