"""Tests for the profiles API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestHealthEndpoints:
    def test_root(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "AI Profile Intelligence"

    def test_app_health(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_profiles_health(self, client: TestClient) -> None:
        response = client.get("/profiles/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestEnrichEndpointValidation:
    """Input validation tests – no external calls required."""

    def test_missing_identifier_returns_422(self, client: TestClient) -> None:
        """Neither linkedin_url nor full_name → validation error."""
        response = client.post("/profiles/enrich", json={})
        assert response.status_code == 422

    def test_web_urls_without_name_or_linkedin_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/profiles/enrich",
            json={"web_urls": ["https://example.com"]},
        )
        assert response.status_code == 422

    def test_invalid_linkedin_url_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/profiles/enrich",
            json={"linkedin_url": "not-a-url"},
        )
        assert response.status_code == 422

    def test_full_name_only_is_valid(self, client: TestClient) -> None:
        """A name-only request should succeed (returns empty profile, no API key)."""
        response = client.post(
            "/profiles/enrich",
            json={"full_name": "Jane Doe"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data
        assert data["profile"]["full_name"] == "Jane Doe"

    def test_linkedin_url_only_is_valid(self, client: TestClient) -> None:
        """A LinkedIn-URL-only request should succeed (no API key → empty profile)."""
        response = client.post(
            "/profiles/enrich",
            json={"linkedin_url": "https://linkedin.com/in/janedoe"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data

    def test_full_name_with_company(self, client: TestClient) -> None:
        response = client.post(
            "/profiles/enrich",
            json={"full_name": "Jane Doe", "company": "Acme Corp"},
        )
        assert response.status_code == 200

    def test_response_schema_fields_present(self, client: TestClient) -> None:
        response = client.post(
            "/profiles/enrich",
            json={"full_name": "John Smith"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data
        assert "sources_used" in data
        assert "errors" in data
        assert isinstance(data["sources_used"], list)
        assert isinstance(data["errors"], list)
