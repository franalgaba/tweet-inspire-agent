"""Estimate how a piece of content could impact health metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from twitter_agent.models.schemas import ContentType


@dataclass
class HealthImpact:
    impacts: list[dict[str, object]]
    followups: list[str]


def estimate_health_impact(
    *,
    content: str | list[str],
    content_type: ContentType,
    virality_components: dict[str, float],
) -> HealthImpact:
    texts = content if isinstance(content, list) else [content]
    lengths = [len(text.strip()) for text in texts if text.strip()]
    avg_length = sum(lengths) / len(lengths) if lengths else 0

    share_potential = virality_components.get("share_potential", 0.0)
    reply_potential = virality_components.get("reply_potential", 0.0)
    dwell_potential = virality_components.get("dwell_potential", 0.0)
    clarity = virality_components.get("clarity", 0.0)
    negative_risk = virality_components.get("negative_risk", 0.0)

    length_score = _length_score(avg_length, content_type)

    impacts: list[dict[str, object]] = []

    share_delta = round(share_potential * 0.2, 2)
    if share_delta > 0.03:
        impacts.append(
            {
                "metric": "shareability",
                "delta": share_delta,
                "reason": "Structured insight increases the chance of reposts and shares.",
            }
        )

    conv_base = reply_potential + (0.2 if content_type in {ContentType.REPLY, ContentType.QUOTE} else 0.0)
    conversation_delta = round(min(1.0, conv_base) * 0.15, 2)
    if conversation_delta > 0.03:
        impacts.append(
            {
                "metric": "conversation_balance",
                "delta": conversation_delta,
                "reason": "Clear opinion or prompt can drive replies and discussion.",
            }
        )

    format_delta = round(((length_score + clarity) / 2) * 0.1, 2)
    if format_delta > 0.02:
        impacts.append(
            {
                "metric": "format_fit",
                "delta": format_delta,
                "reason": "Length and readability align with high-performing formats.",
            }
        )

    engagement_delta = round((1 - negative_risk) * 0.08, 2)
    if negative_risk > 0.6:
        impacts.append(
            {
                "metric": "engagement_quality",
                "delta": -0.05,
                "reason": "High risk of negative feedback could reduce engagement quality.",
            }
        )
    elif engagement_delta > 0.02:
        impacts.append(
            {
                "metric": "engagement_quality",
                "delta": engagement_delta,
                "reason": "Lower negative-signal risk can lift overall engagement quality.",
            }
        )

    followups = _followup_suggestions(
        content_type=content_type,
        share_potential=share_potential,
        reply_potential=reply_potential,
        dwell_potential=dwell_potential,
    )

    return HealthImpact(impacts=impacts[:4], followups=followups[:4])


def _length_score(avg_length: float, content_type: ContentType) -> float:
    if content_type == ContentType.REPLY:
        ideal_min, ideal_max = 60, 200
    elif content_type == ContentType.QUOTE:
        ideal_min, ideal_max = 80, 200
    elif content_type == ContentType.THREAD:
        ideal_min, ideal_max = 120, 260
    else:
        ideal_min, ideal_max = 100, 220

    min_value, max_value = 30, 280
    if avg_length <= min_value or avg_length >= max_value:
        return 0.0
    if avg_length < ideal_min:
        return (avg_length - min_value) / max(ideal_min - min_value, 1)
    if avg_length > ideal_max:
        return max(0.0, (max_value - avg_length) / max(max_value - ideal_max, 1))
    return 1.0


def _followup_suggestions(
    *,
    content_type: ContentType,
    share_potential: float,
    reply_potential: float,
    dwell_potential: float,
) -> list[str]:
    suggestions: list[str] = []

    if share_potential < 0.6:
        suggestions.append("Framework or checklist post")
    if reply_potential < 0.6:
        suggestions.append("Opinionated reply prompt")
    if dwell_potential < 0.6:
        suggestions.append("Mini-thread (3–5 tweets) with a strong hook")

    if content_type == ContentType.THREAD:
        suggestions.append("Single crisp insight tweet")
        suggestions.append("Quote tweet with a fresh angle")
    elif content_type == ContentType.TWEET:
        suggestions.append("Short thread expanding this idea")
        suggestions.append("Reply to a top post in your niche")
    else:
        suggestions.append("Standalone tweet with a clear takeaway")

    # Deduplicate while preserving order
    deduped: list[str] = []
    for item in suggestions:
        if item not in deduped:
            deduped.append(item)
    return deduped
