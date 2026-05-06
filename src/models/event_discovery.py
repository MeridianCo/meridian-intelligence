from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


CostFilter = Literal["free", "paid", "any"]


class EventDiscoveryQuery(BaseModel):
    query: str | None = Field(default=None, description="Free-text search keywords.")
    city: str | None = Field(default=None, description="City name to bias or filter results.")
    latitude: float | None = Field(default=None, description="Latitude for geo search.")
    longitude: float | None = Field(default=None, description="Longitude for geo search.")
    radius_km: int = Field(default=25, ge=1, le=500, description="Search radius in kilometers.")
    start_date: date | None = Field(default=None, description="Earliest event start date (inclusive).")
    end_date: date | None = Field(default=None, description="Latest event start date (inclusive).")
    cost: CostFilter = Field(default="any", description="Cost filter.")
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return.")
    providers: list[str] | None = Field(
        default=None,
        description="Optional provider allow-list override (e.g. ['serpapi','ticketmaster']).",
    )


class ExternalEventResult(BaseModel):
    source: str
    external_id: str | None = None
    external_url: str | None = None

    title: str
    description: str | None = None

    location_name: str | None = None
    address: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: str | None = None

    cost_label: str | None = None
    is_free: bool | None = None
    image_url: str | None = None

    category_labels: list[str] = Field(default_factory=list)
    relevance_reasons: list[str] = Field(default_factory=list)


class EventDiscoveryResponse(BaseModel):
    results: list[ExternalEventResult] = Field(default_factory=list)
    provider_errors: dict[str, str] = Field(default_factory=dict)

