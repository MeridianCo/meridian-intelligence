import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# routes
from src.api.routes import root_router, enrich_router, events_scrape_router, event_discovery_router

# Load environment variables from .env if present.
load_dotenv()

# init fastapi app
app = FastAPI(title="Profile Intelligience Engine API")

# cors midware
app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

# include routers for each endpoint
app.include_router(root_router)
app.include_router(enrich_router, prefix="/enrich")
app.include_router(events_scrape_router, prefix="/events/scrape")
app.include_router(event_discovery_router, prefix="/events/discovery")

# (to be replaced by docker command in prod)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
