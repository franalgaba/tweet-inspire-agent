"""Data models and schemas for Twitter Agent."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ContentType(str, Enum):
    """Types of content that can be generated."""

    TWEET = "tweet"
    THREAD = "thread"
    REPLY = "reply"
    QUOTE = "quote"


class UserInfo(BaseModel):
    """Twitter user information."""

    username: str
    user_id: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    tweet_count: Optional[int] = None


class Tweet(BaseModel):
    """Tweet data model."""

    tweet_id: str
    text: str
    created_at: Optional[datetime] = None
    author_username: str
    like_count: Optional[int] = None
    retweet_count: Optional[int] = None
    reply_count: Optional[int] = None
    quote_count: Optional[int] = None
    is_reply: bool = False
    is_quote: bool = False
    referenced_tweet_id: Optional[str] = None


class VoiceProfile(BaseModel):
    """Analyzed voice/persona profile."""

    username: str
    writing_style: str = Field(description="Description of writing style")
    tone: str = Field(description="Tone characteristics")
    common_topics: list[str] = Field(default_factory=list, description="Frequently discussed topics")
    hashtag_usage: dict[str, int] = Field(default_factory=dict, description="Frequency of hashtags")
    average_tweet_length: Optional[int] = None
    engagement_patterns: dict[str, Any] = Field(default_factory=dict, description="Engagement patterns")
    analyzed_at: datetime = Field(default_factory=datetime.now)


class ContentProposal(BaseModel):
    """Generated content proposal."""

    content_type: ContentType
    content: str | list[str] = Field(description="Tweet text or list of tweets for thread")
    suggested_date: Optional[datetime] = None
    rationale: Optional[str] = Field(None, description="Why this content was proposed")
    based_on: list[str] = Field(default_factory=list, description="Sources used (analytics, calendar, content)")
    engagement_prediction: Optional[dict[str, Any]] = None


class CalendarEvent(BaseModel):
    """Calendar event for scheduling."""

    date: datetime
    title: Optional[str] = None
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    content_suggestions: list[str] = Field(default_factory=list)

