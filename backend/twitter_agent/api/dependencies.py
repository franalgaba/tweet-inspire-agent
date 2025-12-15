"""Dependency injection for FastAPI routes."""

from functools import lru_cache

from twitter_agent.api.config import Settings


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached singleton)."""
    return Settings()

