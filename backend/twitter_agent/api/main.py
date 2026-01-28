"""FastAPI application factory."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from twitter_agent.api.config import Settings
from twitter_agent.api.routers import (
    cache_router,
    generate_router,
    health_router,
    history_router,
    inspire_router,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        settings: Optional settings instance. If not provided, loads from environment.

    Returns:
        Configured FastAPI application instance.
    """
    if settings is None:
        settings = Settings()

    app = FastAPI(title="Twitter Agent API", version="0.1.0")

    # Configure CORS
    origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    # Add frontend URL from settings
    if settings.frontend_url:
        origins.append(settings.frontend_url)

    # Allow all origins in development (default: false for production security)
    if (
        settings.allow_all_origins
        or os.getenv("ALLOW_ALL_ORIGINS", "false").lower() == "true"
    ):
        origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(inspire_router, prefix="/api")
    app.include_router(generate_router, prefix="/api")
    app.include_router(cache_router, prefix="/api")
    app.include_router(history_router, prefix="/api")
    app.include_router(health_router, prefix="/api")

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


# Create default app instance
app = create_app()


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the web server."""
    import uvicorn

    uvicorn.run(
        app,
        host=host,
        port=port,
        timeout_keep_alive=360,  # 6 minutes to support long-running operations
    )
