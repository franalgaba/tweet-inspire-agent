"""In-memory cache for research results to enable quick regeneration."""

import uuid
from datetime import datetime, timedelta
from typing import Optional

# In-memory store for research results
# In production, consider using Redis or a database
_research_store: dict[str, dict] = {}


def store_research(
    username: str,
    tweet_url: Optional[str],
    original_tweet: Optional[dict],
    topic_info: Optional[str],
    extracted_topic: str,
    original_tweet_context: str,
    voice_profile: dict,
    thread_content: Optional[str] = None,
    article_content: Optional[str] = None,
) -> str:
    """
    Store research results and return a research_id.

    Returns:
        research_id string
    """
    research_id = str(uuid.uuid4())
    _research_store[research_id] = {
        "username": username,
        "tweet_url": tweet_url,
        "original_tweet": original_tweet,
        "topic_info": topic_info,
        "extracted_topic": extracted_topic,
        "original_tweet_context": original_tweet_context,
        "voice_profile": voice_profile,
        "thread_content": thread_content,
        "article_content": article_content,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(hours=24),  # Expire after 24 hours
    }
    return research_id


def get_research(research_id: str) -> Optional[dict]:
    """
    Get research results by research_id.

    Returns:
        Research data dict or None if not found/expired
    """
    if research_id not in _research_store:
        return None

    research = _research_store[research_id]

    # Check if expired
    if datetime.now() > research["expires_at"]:
        del _research_store[research_id]
        return None

    return research


def cleanup_expired():
    """Remove expired research entries."""
    now = datetime.now()
    expired_ids = [
        rid for rid, research in _research_store.items() if now > research["expires_at"]
    ]
    for rid in expired_ids:
        del _research_store[rid]

