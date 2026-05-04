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
    </article>
    <article>
      <h2>Weekend music roundup</h2>
      <p>A concert in Edmonton on June 14, 2026 with local bands.</p>
    </article>
  </body>
</html>
"""


class EventScraperTests(unittest.TestCase):
    @patch("src.services.events.event_builder.fetch_url", return_value=BLOG_HTML)
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

    @patch("src.services.events.event_builder.fetch_url", return_value=BLOG_HTML)
    def test_scraper_limits_results(self, _fetch):
        search = EventSearch(
            city="Calgary",
            interests=["AI"],
            sources=[BlogSource(url="https://example.com/blog")],
            max_results=1,
        )

        results = scrape_matching_events(search)

        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
