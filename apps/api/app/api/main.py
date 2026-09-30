"""FastAPI application."""

from __future__ import annotations

from fastapi import Depends, FastAPI

from app.api.deps import require_api_key
from app.api.routes import (
    catalog,
    deals,
    health,
    listings,
    lots,
    portfolio,
    prices,
    settings,
    sources,
    watchlist,
)
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.lifecycle import set_role


def create_app() -> FastAPI:
    set_role("api")
    s = get_settings()
    configure_logging(s.log_level, s.log_json)
    app = FastAPI(title="Pokémon Deal Hunter API", version="0.1.0",
                  docs_url="/docs" if s.environment != "production" else None, redoc_url=None)
    app.include_router(health.router)
    protected = [Depends(require_api_key)]
    for module in (deals, listings, catalog, portfolio, watchlist, prices, sources, settings, lots):
        app.include_router(module.router, prefix="/api/v1", dependencies=protected)
    return app


app = create_app()
