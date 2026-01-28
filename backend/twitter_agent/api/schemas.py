"""Request and response schemas for the web API."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from twitter_agent.models.schemas import ContentType, VoiceProfile, ContentProposal


class AnalyzeRequest(BaseModel):
    """Request schema for analyze endpoint."""

    username: str
    max_tweets: int = 100
    save_profile: bool = False


class AnalyzeResponse(BaseModel):
    """Response schema for analyze endpoint."""

    profile: dict[str, Any]
    saved_path: Optional[str] = None


class GenerateRequest(BaseModel):
    """Request schema for generate endpoint."""

    username: str
    content_type: str = "tweet"
    count: int = 1
    content_dir: Optional[str] = None
    calendar_file: Optional[str] = None
    use_analytics: bool = True
    use_calendar: bool = True
    profile_file: Optional[str] = None
    topic: Optional[str] = None
    thread_count: int = 5


class GenerateResponse(BaseModel):
    """Response schema for generate endpoint."""

    proposals: list[dict[str, Any]]


class InspireRequest(BaseModel):
    """Request schema for inspire endpoint."""

    username: str
    tweet_url: Optional[str] = None
    content_type: str = "tweet"
    profile_file: Optional[str] = None
    thread_count: int = 5
    vibe: Optional[str] = None
    deep_research: bool = False
    use_full_content: bool = False
    context: Optional[str] = None
    topic: Optional[str] = None


class InspireResponse(BaseModel):
    """Response schema for inspire endpoint."""

    original_tweet: Optional[dict[str, Any]] = None
    proposals: dict[str, Any]
    research_id: Optional[str] = None
    prompt: Optional[str] = None


class RegenerateRequest(BaseModel):
    """Request schema for regenerate endpoint."""

    research_id: str
    content_type: str = "all"
    thread_count: int = 5
    vibe: Optional[str] = None
    context: Optional[str] = None
    suggestions: Optional[str] = None


class RegenerateResponse(BaseModel):
    """Response schema for regenerate endpoint."""

    proposals: dict[str, Any]


class ProposeRequest(BaseModel):
    """Request schema for propose endpoint."""

    username: str
    based_on: str = "all"
    content_dir: Optional[str] = None
    calendar_file: Optional[str] = None
    count: int = 5


class ProposeResponse(BaseModel):
    """Response schema for propose endpoint."""

    proposals: list[dict[str, Any]]


class CheckResponse(BaseModel):
    """Response schema for check endpoint."""

    status: dict[str, Any]
    config: dict[str, Any]
    errors: Optional[list[str]] = None


class HealthRequest(BaseModel):
    """Request schema for profile health endpoint."""

    username: str
    profile_file: Optional[str] = None
    max_tweets: int = 200
    prefer_cache_only: bool = False


class HealthResponse(BaseModel):
    """Response schema for profile health endpoint."""

    username: str
    overall_score: float
    scores: dict[str, float]
    metrics: dict[str, Any]
    recommendations: list[dict[str, Any]]
    steps: list[str]


class CacheInfoResponse(BaseModel):
    """Response schema for cache info endpoint."""

    cache_info: dict[str, Any]


class CacheClearResponse(BaseModel):
    """Response schema for cache clear endpoint."""

    success: bool
    message: str


class HistoryEntry(BaseModel):
    """History entry schema."""

    id: int
    tweet_url: Optional[str] = None
    username: str
    original_tweet: Optional[dict[str, Any]] = None
    proposals: dict[str, Any]
    research_id: Optional[str] = None
    created_at: str
    preview: str
    prompt: Optional[str] = None


class HistoryResponse(BaseModel):
    """Response schema for history endpoint."""

    entries: list[dict[str, Any]]


class HistoryEntryResponse(BaseModel):
    """Response schema for single history entry."""

    entry: dict[str, Any]
