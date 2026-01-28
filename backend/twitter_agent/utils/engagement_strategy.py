"""Engagement strategy guidance based on the X algorithm snapshot."""

from __future__ import annotations

from twitter_agent.models.schemas import ContentType

BASE_ENGAGEMENT_STRATEGY = """Optimize for ranking signals while avoiding engagement bait.
- Maximize positive actions: like, reply, repost, share, click, profile click, follow, and dwell.
- Minimize negative actions: hide/not-interested, mute, block, report.
- Make it shareable: deliver a clear takeaway, framework, list, or counterintuitive insight.
- Make it reply-worthy: a strong opinion or specific prompt (no "like/RT if" bait).
- Increase dwell: strong opening line, short lines, and structured flow.
- Avoid spam patterns: excessive hashtags/mentions, ALL CAPS, clickbait, or unsafe content.
"""


def get_engagement_strategy(content_type: ContentType) -> str:
    """Return tailored engagement strategy guidance for the content type."""
    if content_type == ContentType.THREAD:
        return (
            BASE_ENGAGEMENT_STRATEGY
            + "- Thread-specific: hook hard in tweet 1, keep clear transitions, and make each tweet substantial."
        )
    if content_type in (ContentType.REPLY, ContentType.QUOTE):
        return (
            BASE_ENGAGEMENT_STRATEGY
            + "- Reply/quote-specific: add a unique angle, avoid rephrasing, and prefer strong statements over questions."
        )
    return (
        BASE_ENGAGEMENT_STRATEGY
        + "- Single tweet: one clear idea, concise phrasing, and a natural conversational pull."
    )
