import unittest
from unittest.mock import patch

from src.services.events import BlogSource, EventSearch, scrape_matching_events


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


if __name__ == "__main__":
    unittest.main()
