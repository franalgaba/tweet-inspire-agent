"""Profile health scoring and recommendations for X accounts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Optional

from twitter_agent.models.schemas import ContentType, Tweet, UserInfo, VoiceProfile
from twitter_agent.utils.analytics import AnalyticsProcessor
from twitter_agent.utils.virality import ViralityScorer

STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "with",
    "this",
    "you",
    "your",
    "are",
    "was",
    "were",
    "but",
    "not",
    "have",
    "has",
    "had",
    "its",
    "it's",
    "they",
    "them",
    "from",
    "about",
    "into",
    "over",
    "after",
    "before",
    "just",
    "than",
    "then",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "how",
    "also",
    "their",
    "there",
    "here",
    "because",
    "been",
    "being",
    "i",
    "im",
    "i'm",
    "we",
    "our",
    "us",
    "my",
    "me",
}


@dataclass
class ProfileHealthResult:
    """Health scoring output for a profile."""

    username: str
    overall_score: float
    scores: dict[str, float]
    metrics: dict[str, float | int | str | list[int]]
    recommendations: list[dict[str, object]]
    steps: list[str]


def score_profile_health(
    *,
    username: str,
    tweets: list[Tweet],
    user_info: Optional[UserInfo] = None,
    voice_profile: Optional[VoiceProfile] = None,
) -> ProfileHealthResult:
    """Compute profile health scores and recommendations from tweets/profile."""

    analytics = AnalyticsProcessor(tweets)
    patterns = analytics.analyze_engagement_patterns()

    followers = user_info.followers_count if user_info else None
    avg_metrics = patterns.get("average_metrics", {}) if patterns else {}

    avg_likes = float(avg_metrics.get("likes", 0) or 0)
    avg_retweets = float(avg_metrics.get("retweets", 0) or 0)
    avg_replies = float(avg_metrics.get("replies", 0) or 0)
    avg_quotes = float(avg_metrics.get("quotes", 0) or 0)

    avg_engagement = avg_likes + (avg_retweets * 2) + avg_replies + avg_quotes
    engagement_rate = avg_engagement / max(float(followers or 1), 1.0)

    cadence_score, posts_per_week = _score_cadence(tweets)
    engagement_score = _score_engagement_rate(engagement_rate)

    avg_length = _get_average_length(voice_profile, patterns, tweets)
    format_score = _score_length(avg_length)

    reply_ratio = _reply_ratio(tweets)
    conversation_score = _score_reply_ratio(reply_ratio)

    hashtag_rate = _average_hashtags(tweets)
    hashtag_score = _score_hashtags(hashtag_rate)

    link_rate = _average_links(tweets)
    link_score = _score_links(link_rate)

    topic_focus_score, topic_focus_metric = _score_topic_focus(tweets, voice_profile)

    virality_score = _average_virality(tweets)

    profile_score = _score_profile_completeness(user_info)

    scores = {
        "engagement_quality": engagement_score,
        "cadence": cadence_score,
        "topic_focus": topic_focus_score,
        "format_fit": format_score,
        "conversation_balance": conversation_score,
        "shareability": virality_score,
        "hashtag_hygiene": hashtag_score,
        "link_balance": link_score,
        "profile_completeness": profile_score,
    }

    overall_score = _weighted_overall(scores)

    metrics = {
        "followers": int(followers or 0),
        "avg_engagement": round(avg_engagement, 2),
        "engagement_rate": round(engagement_rate, 4),
        "posts_per_week": round(posts_per_week, 2),
        "avg_length": round(avg_length, 1),
        "reply_ratio": round(reply_ratio, 2),
        "hashtag_rate": round(hashtag_rate, 2),
        "link_rate": round(link_rate, 2),
        "topic_focus": round(topic_focus_metric, 3),
        "best_posting_hours": patterns.get("best_posting_hours", []) if patterns else [],
    }

    recommendations = _build_recommendations(scores, metrics)
    steps = _build_steps(scores, metrics)

    return ProfileHealthResult(
        username=username,
        overall_score=overall_score,
        scores=scores,
        metrics=metrics,
        recommendations=recommendations,
        steps=steps,
    )


def _score_engagement_rate(rate: float) -> float:
    if rate >= 0.02:
        return 1.0
    if rate >= 0.01:
        return 0.8
    if rate >= 0.005:
        return 0.6
    if rate >= 0.002:
        return 0.45
    if rate >= 0.001:
        return 0.3
    return 0.2


def _score_cadence(tweets: list[Tweet]) -> tuple[float, float]:
    dated = [t for t in tweets if t.created_at]
    if len(dated) < 2:
        return 0.4, 0.0

    latest = max(t.created_at for t in dated)
    earliest = min(t.created_at for t in dated)
    span_days = max((latest - earliest).days, 1)
    posts_per_week = len(dated) / span_days * 7

    if posts_per_week < 1:
        score = 0.2
    elif posts_per_week < 3:
        score = 0.2 + (posts_per_week - 1) * 0.2
    elif posts_per_week <= 10:
        score = 0.9
    elif posts_per_week <= 20:
        score = 0.7
    else:
        score = 0.5

    return score, posts_per_week


def _get_average_length(
    voice_profile: Optional[VoiceProfile],
    patterns: dict,
    tweets: list[Tweet],
) -> float:
    if voice_profile and voice_profile.average_tweet_length:
        return float(voice_profile.average_tweet_length)
    if patterns and patterns.get("average_tweet_length"):
        return float(patterns["average_tweet_length"])
    if tweets:
        return sum(len(t.text) for t in tweets) / len(tweets)
    return 0.0


def _score_length(avg_length: float) -> float:
    if avg_length <= 0:
        return 0.4
    if avg_length < 60:
        return 0.4
    if avg_length < 90:
        return 0.6
    if avg_length <= 200:
        return 0.95
    if avg_length <= 240:
        return 0.7
    return 0.4


def _reply_ratio(tweets: list[Tweet]) -> float:
    if not tweets:
        return 0.0
    replies = sum(1 for t in tweets if t.is_reply)
    return replies / len(tweets)


def _score_reply_ratio(ratio: float) -> float:
    target = 0.45
    distance = abs(ratio - target)
    score = max(0.2, 1.0 - (distance / target))
    return score


def _average_hashtags(tweets: list[Tweet]) -> float:
    if not tweets:
        return 0.0
    counts = [len(re.findall(r"#\w+", t.text)) for t in tweets]
    return sum(counts) / len(counts)


def _score_hashtags(rate: float) -> float:
    if rate <= 0.3:
        return 1.0
    if rate <= 1.0:
        return 0.85
    if rate <= 2.0:
        return 0.6
    if rate <= 3.0:
        return 0.4
    return 0.2


def _average_links(tweets: list[Tweet]) -> float:
    if not tweets:
        return 0.0
    hits = sum(1 for t in tweets if re.search(r"https?://|www\.", t.text))
    return hits / len(tweets)


def _score_links(rate: float) -> float:
    if 0.05 <= rate <= 0.2:
        return 0.9
    if rate < 0.05:
        return 0.6
    if rate <= 0.35:
        return 0.7
    return 0.4


def _score_topic_focus(
    tweets: list[Tweet],
    voice_profile: Optional[VoiceProfile],
) -> tuple[float, float]:
    if voice_profile and voice_profile.common_topics:
        topic_count = len(voice_profile.common_topics)
        if 3 <= topic_count <= 7:
            return 1.0, float(topic_count)
        if topic_count <= 2:
            return 0.5, float(topic_count)
        if topic_count <= 12:
            return 0.7, float(topic_count)
        return 0.4, float(topic_count)

    tokens = []
    for tweet in tweets:
        cleaned = re.sub(r"https?://\S+", "", tweet.text.lower())
        for token in re.findall(r"\b[a-z]{4,}\b", cleaned):
            if token not in STOPWORDS:
                tokens.append(token)

    if not tokens:
        return 0.4, 0.0

    counts = Counter(tokens)
    total = sum(counts.values())
    top = sum(count for _, count in counts.most_common(5))
    concentration = top / max(total, 1)

    if concentration >= 0.18:
        return 1.0, concentration
    if concentration >= 0.12:
        return 0.8, concentration
    if concentration >= 0.08:
        return 0.6, concentration
    if concentration >= 0.05:
        return 0.4, concentration
    return 0.2, concentration


def _average_virality(tweets: list[Tweet]) -> float:
    if not tweets:
        return 0.4
    scorer = ViralityScorer()
    scores = []
    for tweet in tweets[:20]:
        content_type = ContentType.REPLY if tweet.is_reply else ContentType.TWEET
        scores.append(scorer.score(tweet.text, content_type).score / 100.0)
    return sum(scores) / len(scores) if scores else 0.4


def _score_profile_completeness(user_info: Optional[UserInfo]) -> float:
    if not user_info:
        return 0.5
    bio = user_info.bio or ""
    if len(bio.strip()) >= 80:
        return 1.0
    if len(bio.strip()) >= 20:
        return 0.7
    if len(bio.strip()) > 0:
        return 0.5
    return 0.3


def _weighted_overall(scores: dict[str, float]) -> float:
    weights = {
        "engagement_quality": 0.25,
        "shareability": 0.2,
        "cadence": 0.15,
        "topic_focus": 0.12,
        "format_fit": 0.1,
        "conversation_balance": 0.08,
        "hashtag_hygiene": 0.05,
        "link_balance": 0.03,
        "profile_completeness": 0.02,
    }
    total = sum(weights.values())
    score = sum(scores.get(key, 0.5) * weight for key, weight in weights.items())
    return round((score / max(total, 1e-6)) * 100, 1)


def _build_recommendations(
    scores: dict[str, float],
    metrics: dict[str, float | int | str | list[int]],
) -> list[dict[str, object]]:
    recommendations: list[dict[str, object]] = []

    def add(title: str, priority: str, why: str, actions: list[str]) -> None:
        recommendations.append(
            {
                "title": title,
                "priority": priority,
                "why": why,
                "actions": actions,
            }
        )

    if scores.get("topic_focus", 1.0) < 0.6:
        add(
            "Sharpen topical focus",
            "high",
            "Posts cover too many themes, which weakens recommendation signals.",
            [
                "Pick 2–3 core topics and publish within those for 2 weeks.",
                "Create a recurring series or format to reinforce your niche.",
            ],
        )

    if scores.get("shareability", 1.0) < 0.6:
        add(
            "Increase shareable formats",
            "high",
            "Recent posts are not triggering strong share signals.",
            [
                "Publish 1–2 posts/week that include a framework, checklist, or strong takeaway.",
                "Open with a bold statement before supporting detail.",
            ],
        )

    if scores.get("engagement_quality", 1.0) < 0.6:
        add(
            "Strengthen engagement hooks",
            "high",
            "Average engagement rate is low for the current follower base.",
            [
                "Use sharper hooks and clearer takes (avoid hedging).",
                "End posts with a specific, natural prompt for replies.",
            ],
        )

    if scores.get("cadence", 1.0) < 0.6:
        add(
            "Stabilize posting cadence",
            "medium",
            "Inconsistent posting reduces recency and distribution opportunities.",
            [
                "Aim for 3–7 posts per week for the next month.",
                "Schedule posts during your best-performing hours.",
            ],
        )

    if scores.get("conversation_balance", 1.0) < 0.6:
        add(
            "Balance replies and originals",
            "medium",
            "Conversation signals are not balanced across content.",
            [
                "Keep ~30–50% of weekly posts as replies or quote tweets.",
                "Respond to high-quality threads in your niche.",
            ],
        )

    if scores.get("format_fit", 1.0) < 0.6:
        add(
            "Tighten post length",
            "medium",
            "Average length is outside the best-performing range.",
            [
                "Aim for 100–200 characters on single tweets.",
                "Use short lines or bullets for readability.",
            ],
        )

    if scores.get("hashtag_hygiene", 1.0) < 0.6:
        add(
            "Reduce hashtag usage",
            "low",
            "High hashtag density can look spammy to users.",
            [
                "Limit to 0–1 hashtags per post.",
                "Replace hashtags with plain-language keywords.",
            ],
        )

    if scores.get("link_balance", 1.0) < 0.6:
        add(
            "Increase standalone value",
            "low",
            "Heavy link usage can reduce dwell and share signals.",
            [
                "Include the key takeaway in the post itself.",
                "Use links sparingly and only when adding depth.",
            ],
        )

    if scores.get("profile_completeness", 1.0) < 0.6:
        add(
            "Improve profile clarity",
            "low",
            "A short bio weakens follow conversion.",
            [
                "Add a clear value proposition in your bio.",
                "Highlight your niche and what people gain by following you.",
            ],
        )

    return recommendations[:6]


def _build_steps(
    scores: dict[str, float],
    metrics: dict[str, float | int | str | list[int]],
) -> list[str]:
    steps: list[str] = []
    best_hours = metrics.get("best_posting_hours")

    if scores.get("cadence", 1.0) < 0.7:
        steps.append("Plan a 2-week schedule of 3–7 posts per week.")
    if best_hours:
        hours_str = ", ".join(str(h) + ":00" for h in best_hours[:3])
        steps.append(f"Post during your best hours: {hours_str}.")
    if scores.get("shareability", 1.0) < 0.7:
        steps.append("Publish one framework/list post and one strong-opinion post weekly.")
    if scores.get("conversation_balance", 1.0) < 0.7:
        steps.append("Reply to 3–5 posts in your niche each week.")
    if scores.get("topic_focus", 1.0) < 0.7:
        steps.append("Commit to 2–3 core themes for the next 10 posts.")
    if scores.get("format_fit", 1.0) < 0.7:
        steps.append("Keep single tweets in the 100–200 character range.")

    return steps[:6]
