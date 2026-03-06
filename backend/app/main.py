from fastapi import FastAPI

from .config import get_settings
from .routers import health, sounds, meta


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    # Routers
    app.include_router(health.router)
    app.include_router(sounds.router)
    app.include_router(meta.router)

    return app


app = create_app()

