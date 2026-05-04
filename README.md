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
    "max_results": 10
  }'
```

The response includes each candidate's title, source URL, event URL, all duplicate source/event URLs, duplicate count, snippet, detected dates, matched terms, relevance score, and gathered event details such as description, location, venue, times, prices, and organizer.
