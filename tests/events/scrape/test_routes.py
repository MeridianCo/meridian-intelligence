import unittest
from unittest.mock import patch

from src.api.routes.event_scrape import saved_events


class SavedScrapedEventsRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_saved_events_search_returns_count_and_events(self):
        event = {"title": "Founder AI Night"}

        with patch(
            "src.api.routes.event_scrape.search_saved_events",
            return_value=[event],
        ) as search:
            response = await saved_events(query="AI", city="Calgary", limit=5)

        search.assert_called_once_with(query="AI", city="Calgary", limit=5)
        self.assertEqual(response, {"count": 1, "events": [event]})


if __name__ == "__main__":
    unittest.main()
