"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app


@pytest.fixture()
def test_settings() -> Settings:
    """Settings instance with safe defaults (no real API keys)."""
    return Settings(
        proxycurl_api_key="",
        clearbit_api_key="",
        debug=True,
    )


@pytest.fixture()
def client(test_settings: Settings) -> TestClient:
    """Synchronous TestClient wired to test settings."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    return TestClient(app)
