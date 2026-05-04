import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# routes
from src.api.routes import root_router, enrich_router, events_router

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
app.include_router(events_router, prefix="/events")

# (to be replaced by docker command in prod)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
