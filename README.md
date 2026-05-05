# ai-profile-intelligience
Consolidate information about a profile from multiple sources (primarily LinkedIn) so the rest of the system has structured context.

## Event blog scraper

The event discovery service scrapes blog or local listing pages and ranks date-bearing event snippets by city, nearby locations, and interests.

Scraper implementation: `src/services/shared/scrapers/event_builder.py`

Run the API:

```bash
uvicorn src.main:app --reload
```

Search for matching events:

```bash
curl -X POST http://localhost:8000/events/search \
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
