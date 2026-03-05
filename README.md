# ai-profile-intelligience

A Python **FastAPI** microservice that consolidates and enriches professional profiles from multiple sources (primarily LinkedIn and public web pages) into a single, structured context object that the rest of the system can consume.

---

## Features

- **LinkedIn enrichment** via [Proxycurl](https://nubela.co/proxycurl) (URL-based or name-based lookup)
- **Web scraping** of arbitrary public pages (personal sites, bio pages, etc.)
- **Profile consolidation** – merges all sources, deduplicates entries, and surfaces a unified `Profile` model
- **FastAPI** REST API with automatic OpenAPI docs at `/docs`
- **Pydantic v2** models with strict validation
- **In-process cache** (configurable TTL) to avoid redundant external calls
- **Retry logic** with exponential back-off for external HTTP calls
- Gracefully degrades when optional API keys are not configured

---

## Quick Start

### 1. Install dependencies

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your Proxycurl API key (optional but recommended)
```

### 3. Run the server

```bash
uvicorn app.main:app --reload
```

The API is now available at <http://localhost:8000>.  
Interactive docs: <http://localhost:8000/docs>

### 4. Run with Docker

```bash
docker-compose up --build
```

---

## API Reference

### `POST /profiles/enrich`

Consolidate and enrich a professional profile.

**Request body** (JSON):

| Field          | Type            | Required | Description                                                  |
|----------------|-----------------|----------|--------------------------------------------------------------|
| `linkedin_url` | `string` (URL)  | *        | Public LinkedIn profile URL                                  |
| `full_name`    | `string`        | *        | Full name of the person                                      |
| `company`      | `string`        | No       | Current employer – improves name-based lookup quality        |
| `web_urls`     | `list[string]`  | No       | Additional public pages to scrape (personal site, bio, etc.) |

\* At least one of `linkedin_url` or `full_name` is required.

**Example request:**

```json
{
  "linkedin_url": "https://linkedin.com/in/janedoe",
  "web_urls": ["https://janedoe.dev/about"]
}
```

**Example response:**

```json
{
  "profile": {
    "full_name": "Jane Doe",
    "headline": "Senior Engineer at Acme",
    "summary": "Passionate engineer.",
    "location": "San Francisco",
    "email": "jane@example.com",
    "social_links": { "linkedin": "https://linkedin.com/in/janedoe" },
    "work_experience": [
      {
        "title": "Senior Engineer",
        "company": "Acme Corp",
        "location": "San Francisco, CA",
        "date_range": { "start": "2020-03-01", "end": null, "is_current": true },
        "source": "linkedin"
      }
    ],
    "education": [],
    "skills": [{ "name": "Python", "endorsements": 0, "source": "linkedin" }],
    "sources_used": ["linkedin", "web"],
    "raw_web_snippets": ["Jane Doe – Engineer at Acme Corp ..."]
  },
  "sources_used": ["linkedin", "web"],
  "errors": []
}
```

### `GET /health`

Returns `{"status": "ok"}` when the service is running.

### `GET /profiles/health`

Returns `{"status": "ok"}` when the profiles router is healthy.

---

## Configuration

All settings are read from environment variables (or `.env`):

| Variable             | Default | Description                                         |
|----------------------|---------|-----------------------------------------------------|
| `PROXYCURL_API_KEY`  | `""`    | Proxycurl API key for LinkedIn enrichment           |
| `CLEARBIT_API_KEY`   | `""`    | Clearbit API key (reserved for future enrichment)   |
| `HTTP_TIMEOUT`       | `15.0`  | Seconds before an outgoing HTTP request times out   |
| `HTTP_MAX_RETRIES`   | `3`     | Maximum retry attempts for transient HTTP failures  |
| `CACHE_TTL_SECONDS`  | `3600`  | Time-to-live for cached profile results (seconds)   |
| `CACHE_MAX_SIZE`     | `256`   | Maximum number of profiles held in the in-process cache |
| `DEBUG`              | `false` | Enable debug logging                                |

---

## Development

### Install dev dependencies

```bash
pip install -r requirements-dev.txt
```

### Run tests

```bash
pytest
```

### Lint

```bash
ruff check .
```

---

## Project Structure

```
ai-profile-intelligience/
├── app/
│   ├── main.py              # FastAPI app factory & entry point
│   ├── config.py            # Pydantic-settings configuration
│   ├── schemas.py           # Request / response schemas
│   ├── models/
│   │   └── __init__.py      # Pydantic domain models (Profile, WorkExperience, …)
│   ├── routers/
│   │   └── profiles.py      # /profiles API endpoints
│   └── services/
│       ├── linkedin.py      # LinkedIn enrichment via Proxycurl
│       ├── web_scraper.py   # Public web page scraping
│       └── enricher.py      # Orchestration & consolidation
├── tests/
│   ├── conftest.py
│   ├── test_profiles.py     # Endpoint tests
│   └── test_services.py     # Service unit tests
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```
