from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from src.models.event_discovery import EventDiscoveryQuery, EventDiscoveryResponse, ExternalEventResult
from src.services.events.integrations.eventbrite import EventbriteProvider
from src.services.events.integrations.serpapi import SerpApiGoogleEventsProvider
from src.services.events.integrations.ticketmaster import TicketmasterDiscoveryProvider


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    enabled: bool
    provider: object


class EventDiscoveryService:
    def __init__(self) -> None:
        self._providers = self._build_providers()

    def available_providers(self) -> list[str]:
        return sorted(self._providers.keys())

    def enabled_providers(self) -> list[str]:
        return sorted([name for name, spec in self._providers.items() if spec.enabled])

    def _build_providers(self) -> dict[str, ProviderSpec]:
        # Dev-friendly defaults: enabled unless explicitly disabled.
        serpapi_enabled = _env_bool("EVENT_DISCOVERY_ENABLE_SERPAPI", True)
        # Eventbrite public search was shut down; keep disabled by default unless explicitly enabled.
        eventbrite_enabled = _env_bool("EVENT_DISCOVERY_ENABLE_EVENTBRITE", False)
        ticketmaster_enabled = _env_bool("EVENT_DISCOVERY_ENABLE_TICKETMASTER", True)

        return {
            "serpapi": ProviderSpec(
                name="serpapi",
                enabled=serpapi_enabled,
                provider=SerpApiGoogleEventsProvider(api_key=os.getenv("SERPAPI_API_KEY")),
            ),
            "eventbrite": ProviderSpec(
                name="eventbrite",
                enabled=eventbrite_enabled,
                provider=EventbriteProvider(private_token=os.getenv("EVENTBRITE_PRIVATE_TOKEN")),
            ),
            "ticketmaster": ProviderSpec(
                name="ticketmaster",
                enabled=ticketmaster_enabled,
                provider=TicketmasterDiscoveryProvider(api_key=os.getenv("TICKETMASTER_API_KEY")),
            ),
        }

    async def search(self, query: EventDiscoveryQuery) -> EventDiscoveryResponse:
        allowed = None
        if query.providers:
            allowed = {provider.strip().lower() for provider in query.providers if provider.strip()}

        tasks: list[asyncio.Task[list[ExternalEventResult]]] = []
        task_names: list[str] = []
        provider_errors: dict[str, str] = {}
        for name, spec in self._providers.items():
            if not spec.enabled:
                continue
            if allowed is not None and name not in allowed:
                continue

            # Provider-specific input requirements to avoid broad/expensive queries.
            if name == "serpapi" and not (query.city and query.city.strip()):
                provider_errors[name] = "city is required for serpapi (google_events) location filtering."
                continue

            provider = spec.provider
            if not hasattr(provider, "search"):
                continue
            tasks.append(asyncio.create_task(provider.search(query)))  # type: ignore[attr-defined]
            task_names.append(name)

        results: list[ExternalEventResult] = []
        if not tasks:
            provider_errors.setdefault("_service", "No providers enabled (or inputs were insufficient for all enabled providers).")
            return EventDiscoveryResponse(results=[], provider_errors=provider_errors)

        completed = await asyncio.gather(*tasks, return_exceptions=True)
        for name, outcome in zip(task_names, completed, strict=True):
            if isinstance(outcome, Exception):
                provider_errors[name] = str(outcome)
                continue
            results.extend(outcome)

        if query.limit and len(results) > query.limit:
            results = results[: query.limit]
        return EventDiscoveryResponse(results=results, provider_errors=provider_errors)
