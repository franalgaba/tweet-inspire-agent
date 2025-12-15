"""Analytics processor for engagement patterns and content insights."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional

from twitter_agent.models.schemas import Tweet


class AnalyticsProcessor:
    """Process engagement analytics from tweets."""

    def __init__(self, tweets: list[Tweet]):
        """
        Initialize analytics processor.

        Args:
            tweets: List of tweets to analyze
        """
        self.tweets = tweets

    def analyze_engagement_patterns(self) -> dict[str, any]:
        """
        Analyze engagement patterns from tweets.

        Returns:
            Dictionary with engagement insights
        """
        if not self.tweets:
            return {}

        # Calculate average engagement metrics
        total_likes = sum(t.like_count or 0 for t in self.tweets)
        total_retweets = sum(t.retweet_count or 0 for t in self.tweets)
        total_replies = sum(t.reply_count or 0 for t in self.tweets)
        total_quotes = sum(t.quote_count or 0 for t in self.tweets)

        avg_likes = total_likes / len(self.tweets) if self.tweets else 0
        avg_retweets = total_retweets / len(self.tweets) if self.tweets else 0
        avg_replies = total_replies / len(self.tweets) if self.tweets else 0
        avg_quotes = total_quotes / len(self.tweets) if self.tweets else 0

        # Find top performing tweets
        top_tweets = sorted(
            self.tweets,
            key=lambda t: (t.like_count or 0) + (t.retweet_count or 0) * 2,
            reverse=True,
        )[:10]

        # Analyze best posting times
        hourly_engagement = defaultdict(lambda: {"likes": 0, "retweets": 0, "count": 0})
        for tweet in self.tweets:
            if tweet.created_at:
                hour = tweet.created_at.hour
                hourly_engagement[hour]["likes"] += tweet.like_count or 0
                hourly_engagement[hour]["retweets"] += tweet.retweet_count or 0
                hourly_engagement[hour]["count"] += 1

        # Find best hours
        best_hours = sorted(
            hourly_engagement.items(),
            key=lambda x: (x[1]["likes"] + x[1]["retweets"] * 2) / max(x[1]["count"], 1),
            reverse=True,
        )[:3]

        # Analyze content length
        tweet_lengths = [len(t.text) for t in self.tweets]
        avg_length = sum(tweet_lengths) / len(tweet_lengths) if tweet_lengths else 0

        # Analyze hashtag usage
        hashtag_counts = Counter()
        for tweet in self.tweets:
            words = tweet.text.split()
            for word in words:
                if word.startswith("#"):
                    hashtag_counts[word.lower()] += 1

        top_hashtags = [tag for tag, count in hashtag_counts.most_common(10)]

        # Analyze reply vs original tweets
        reply_tweets = [t for t in self.tweets if t.is_reply]
        original_tweets = [t for t in self.tweets if not t.is_reply]

        reply_avg_engagement = (
            sum((t.like_count or 0) + (t.retweet_count or 0) for t in reply_tweets)
            / len(reply_tweets)
            if reply_tweets
            else 0
        )
        original_avg_engagement = (
            sum((t.like_count or 0) + (t.retweet_count or 0) for t in original_tweets)
            / len(original_tweets)
            if original_tweets
            else 0
        )

        return {
            "average_metrics": {
                "likes": round(avg_likes, 2),
                "retweets": round(avg_retweets, 2),
                "replies": round(avg_replies, 2),
                "quotes": round(avg_quotes, 2),
            },
            "top_performing_tweets": [
                {
                    "text": t.text[:100] + "..." if len(t.text) > 100 else t.text,
                    "likes": t.like_count,
                    "retweets": t.retweet_count,
                }
                for t in top_tweets[:5]
            ],
            "best_posting_hours": [hour for hour, _ in best_hours],
            "average_tweet_length": round(avg_length, 0),
            "top_hashtags": top_hashtags,
            "engagement_by_type": {
                "replies": round(reply_avg_engagement, 2),
                "original": round(original_avg_engagement, 2),
            },
            "total_tweets_analyzed": len(self.tweets),
        }

    def get_insights_summary(self) -> str:
        """
        Get a formatted summary of analytics insights.

        Returns:
            Formatted string with insights
        """
        patterns = self.analyze_engagement_patterns()
        if not patterns:
            return "No analytics data available."

        insights = []
        insights.append("ENGAGEMENT ANALYTICS SUMMARY:")
        insights.append(f"- Average likes per tweet: {patterns['average_metrics']['likes']}")
        insights.append(f"- Average retweets per tweet: {patterns['average_metrics']['retweets']}")
        insights.append(f"- Average tweet length: {patterns['average_tweet_length']} characters")

        if patterns.get("best_posting_hours"):
            hours_str = ", ".join(str(h) for h in patterns["best_posting_hours"])
            insights.append(f"- Best posting hours: {hours_str}:00")

        if patterns.get("top_hashtags"):
            hashtags_str = ", ".join(patterns["top_hashtags"][:5])
            insights.append(f"- Most used hashtags: {hashtags_str}")

        if patterns.get("engagement_by_type"):
            eng_type = patterns["engagement_by_type"]
            insights.append(
                f"- Replies vs Original engagement: {eng_type['replies']} vs {eng_type['original']}"
            )

        if patterns.get("top_performing_tweets"):
            insights.append("\nTOP PERFORMING CONTENT PATTERNS:")
            for i, tweet in enumerate(patterns["top_performing_tweets"][:3], 1):
                insights.append(f"{i}. {tweet['text']} (Likes: {tweet['likes']})")

        return "\n".join(insights)

