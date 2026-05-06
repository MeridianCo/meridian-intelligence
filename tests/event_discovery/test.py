import json
import unittest
from unittest.mock import patch

from src.models.event_discovery import EventDiscoveryQuery
from src.services.events.event_discovery import EventDiscoveryService


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class EventDiscoveryServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_provider_errors_when_missing_keys(self):
        with patch.dict("os.environ", {}, clear=True):
            service = EventDiscoveryService()
            response = await service.search(EventDiscoveryQuery(query="ai", city="Calgary", limit=5))
            self.assertEqual(response.results, [])
            self.assertIn("serpapi", response.provider_errors)
            self.assertIn("eventbrite", response.provider_errors)
            self.assertIn("ticketmaster", response.provider_errors)

    async def test_serpapi_normalizes_events(self):
        serp_payload = {
            "events_results": [
                {
                    "title": "Founder AI Night",
                    "link": "https://example.com/event",
                    "date": {"start_date": "2026-06-12T18:30:00-06:00"},
                    "address": ["Platform Calgary", "Calgary, AB"],
                    "thumbnail": "https://example.com/thumb.jpg",
                }
            ]
        }

        def fake_urlopen(_request, timeout=15):
            return FakeResponse(serp_payload)

        with patch.dict("os.environ", {"SERPAPI_API_KEY": "k"}):
            with patch("src.services.events.integrations.serpapi.urlopen", side_effect=fake_urlopen):
                service = EventDiscoveryService()
                response = await service.search(EventDiscoveryQuery(query="ai", city="Calgary", limit=5, providers=["serpapi"]))

        self.assertEqual(len(response.results), 1)
        event = response.results[0]
        self.assertEqual(event.source, "serpapi")
        self.assertEqual(event.title, "Founder AI Night")
        self.assertEqual(event.external_url, "https://example.com/event")
        self.assertTrue(event.relevance_reasons)

    async def test_eventbrite_lists_events_by_org(self):
        org_payload = {"organizations": [{"id": "123"}]}
        events_payload = {
            "events": [
                {
                    "id": "evt_1",
                    "url": "https://eventbrite.com/e/evt_1",
                    "name": {"text": "Calgary AI Night"},
                    "description": {"text": "Networking for founders."},
                    "start": {"utc": "2026-06-12T00:30:00Z", "timezone": "America/Edmonton"},
                    "end": {"utc": "2026-06-12T03:00:00Z", "timezone": "America/Edmonton"},
                    "logo": {"url": "https://example.com/logo.jpg"},
                }
            ]
        }

        def fake_urlopen(request, timeout=15):
            url = getattr(request, "full_url", "") or str(request)
            if url.endswith("/v3/users/me/organizations/"):
                return FakeResponse(org_payload)
            if "/v3/organizations/123/events/" in url:
                return FakeResponse(events_payload)
            raise AssertionError(f"Unexpected URL: {url}")

        with patch.dict("os.environ", {"EVENTBRITE_PRIVATE_TOKEN": "t"}):
            with patch("src.services.events.integrations.eventbrite.urlopen", side_effect=fake_urlopen):
                service = EventDiscoveryService()
                response = await service.search(
                    EventDiscoveryQuery(query="AI", city="Calgary", limit=5, providers=["eventbrite"])
                )

        self.assertEqual(len(response.results), 1)
        event = response.results[0]
        self.assertEqual(event.source, "eventbrite")
        self.assertEqual(event.external_id, "evt_1")
        self.assertIn("Calgary AI Night", event.title)
