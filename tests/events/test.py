import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.services.events import BlogSource, EventSearch, discover_event_sources, scrape_matching_events
from src.db.event_store import list_saved_events, save_event_candidates


BLOG_HTML = """
<html>
  <head><title>Calgary Founder Blog</title></head>
  <body>
    <article>
      <h2><a href="/events/founder-ai-night">Founder AI Night</a></h2>
      <p>Founder AI Night is a networking event in Calgary on June 12, 2026.</p>
      <p>Expect practical AI demos, healthcare startup operators, and investors.</p>
      <p>Location: Platform Calgary. Hosted by Startup TNT. Runs 6:30 pm to 9:00 pm. Tickets from $25.</p>
    </article>
    <article>
      <h2>Weekend music roundup</h2>
      <p>A concert in Edmonton on June 14, 2026 with local bands.</p>
    </article>
  </body>
</html>
"""

DUPLICATE_BLOGS = {
    "https://one.example/blog": """
    <html><body>
      <h2><a href="/founder-ai-night">Founder AI Night</a></h2>
      <p>Founder AI Night is a networking event in Calgary on June 12, 2026.</p>
      <p>AI demos for healthcare founders.</p>
    </body></html>
    """,
    "https://two.example/events": """
    <html><body>
      <h2><a href="/calendar/founder-ai-night">The Founder AI Night Event</a></h2>
      <p>The Founder AI Night Event happens in Calgary on June 12, 2026.</p>
      <p>Healthcare startup leaders and AI builders will meet.</p>
    </body></html>
    """,
}

SEED_HTML = """
<html><body>
  <a href="/calgary-events">Calgary events calendar</a>
  <a href="/blog/ai-founder-workshops">AI founder workshops blog</a>
  <a href="https://external.example/events">External events</a>
  <a href="/contact">Contact</a>
</body></html>
"""

JSON_LD_HTML = """
<html><head>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "Calgary AI Healthcare Summit",
    "description": "A Calgary conference for AI healthcare founders.",
    "startDate": "2026-06-20T09:00:00-06:00",
    "endDate": "2026-06-20T17:00:00-06:00",
    "url": "https://example.com/events/ai-healthcare-summit",
    "image": "https://example.com/summit.jpg",
    "location": {
      "@type": "Place",
      "name": "Calgary Innovation Centre",
      "address": {
        "@type": "PostalAddress",
        "addressLocality": "Calgary",
        "addressRegion": "AB"
      }
    },
    "organizer": {"@type": "Organization", "name": "Health AI Alberta"},
    "offers": {
      "@type": "Offer",
      "url": "https://example.com/tickets",
      "price": "49",
      "priceCurrency": "CAD"
    }
  }
  </script>
</head><body></body></html>
"""


class EventScraperTests(unittest.TestCase):
    @patch("src.services.shared.scrapers.event_builder.fetch_url", return_value=BLOG_HTML)
    def test_scraper_scores_city_and_interest_matches(self, _fetch):
        search = EventSearch(
            city="Calgary",
            interests=["AI", "healthcare"],
            nearby_locations=["Airdrie"],
            sources=[BlogSource(url="https://example.com/blog")],
            max_results=5,
        )

        results = scrape_matching_events(search)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].title, "Founder AI Night")
        self.assertEqual(results[0].event_url, "https://example.com/events/founder-ai-night")
        self.assertIn("June 12, 2026", results[0].dates)
        self.assertIn("Calgary", results[0].matched_terms)
        self.assertIn("AI", results[0].matched_terms)
        self.assertIn("healthcare", results[0].matched_terms)
        self.assertEqual(results[0].details.location, "Calgary")
        self.assertEqual(results[0].details.venue, "Platform Calgary")
        self.assertEqual(results[0].details.organizer, "Startup TNT")
        self.assertEqual(results[0].details.times, ["6:30 pm", "9:00 pm"])
        self.assertEqual(results[0].details.prices, ["Tickets from $25"])

    @patch("src.services.shared.scrapers.event_builder.fetch_url", return_value=BLOG_HTML)
    def test_scraper_limits_results(self, _fetch):
        search = EventSearch(
            city="Calgary",
            interests=["AI"],
            sources=[BlogSource(url="https://example.com/blog")],
            max_results=1,
        )

        results = scrape_matching_events(search)

        self.assertEqual(len(results), 1)

    @patch("src.services.shared.scrapers.event_builder.fetch_url", side_effect=lambda url: DUPLICATE_BLOGS[url])
    def test_scraper_merges_duplicate_events_across_sites(self, _fetch):
        search = EventSearch(
            city="Calgary",
            interests=["AI", "healthcare"],
            sources=[
                BlogSource(url="https://one.example/blog"),
                BlogSource(url="https://two.example/events"),
            ],
        )

        results = scrape_matching_events(search)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].duplicate_count, 2)
        self.assertEqual(
            results[0].source_urls,
            ["https://one.example/blog", "https://two.example/events"],
        )
        self.assertEqual(
            results[0].event_urls,
            [
                "https://one.example/founder-ai-night",
                "https://two.example/calendar/founder-ai-night",
            ],
        )

    @patch("src.services.shared.scrapers.event_builder.fetch_url", return_value=SEED_HTML)
    def test_discovers_event_sources_from_seed_pages(self, _fetch):
        search = EventSearch(
            city="Calgary",
            interests=["AI"],
            seed_urls=["https://example.com"],
            max_discovered_sources=2,
        )

        sources = discover_event_sources(search)

        self.assertEqual(
            set(source.url for source in sources[:2]),
            {
                "https://example.com/blog/ai-founder-workshops",
                "https://example.com/calgary-events",
            },
        )

    @patch("src.services.shared.scrapers.event_builder.fetch_url", side_effect=lambda url: DUPLICATE_BLOGS[url])
    def test_saves_events_by_stable_fingerprint(self, _fetch):
        search = EventSearch(
            city="Calgary",
            interests=["AI", "healthcare"],
            sources=[
                BlogSource(url="https://one.example/blog"),
                BlogSource(url="https://two.example/events"),
            ],
        )
        results = scrape_matching_events(search)

        with TemporaryDirectory() as temp_dir:
            db_path = f"{temp_dir}/events.sqlite3"
            save_event_candidates(results, db_path)
            save_event_candidates(results, db_path)
            saved = list_saved_events(db_path)

        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["fingerprint"], results[0].fingerprint)
        self.assertEqual(
            saved[0]["source_urls"],
            ["https://one.example/blog", "https://two.example/events"],
        )

    @patch("src.services.shared.scrapers.event_builder.fetch_url", return_value=JSON_LD_HTML)
    def test_extracts_schema_org_event_json_ld(self, _fetch):
        search = EventSearch(
            city="Calgary",
            interests=["AI", "healthcare"],
            sources=[BlogSource(url="https://example.com/events")],
        )

        results = scrape_matching_events(search)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Calgary AI Healthcare Summit")
        self.assertEqual(results[0].event_url, "https://example.com/events/ai-healthcare-summit")
        self.assertEqual(results[0].details.venue, "Calgary Innovation Centre")
        self.assertEqual(results[0].details.location, "Calgary, AB")
        self.assertEqual(results[0].details.organizer, "Health AI Alberta")
        self.assertEqual(results[0].details.start_date, "2026-06-20T09:00:00-06:00")
        self.assertEqual(results[0].details.end_date, "2026-06-20T17:00:00-06:00")
        self.assertEqual(results[0].details.image_url, "https://example.com/summit.jpg")
        self.assertEqual(results[0].details.ticket_url, "https://example.com/tickets")
        self.assertEqual(results[0].details.prices, ["49 CAD"])


if __name__ == "__main__":
    unittest.main()
