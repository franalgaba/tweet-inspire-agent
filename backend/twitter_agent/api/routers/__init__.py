"""API routers."""

from twitter_agent.api.routers.cache import router as cache_router
from twitter_agent.api.routers.generate import router as generate_router
from twitter_agent.api.routers.health import router as health_router
from twitter_agent.api.routers.history import router as history_router
from twitter_agent.api.routers.inspire import router as inspire_router

__all__ = [
    "inspire_router",
    "generate_router",
    "cache_router",
    "history_router",
    "health_router",
]
