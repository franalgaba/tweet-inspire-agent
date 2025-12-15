"""Voice analyzer for extracting persona/style patterns from tweets."""

import json
from typing import Optional

from loguru import logger

from twitter_agent.clients.twitter import TwitterAPIClient
from twitter_agent.llm.ollama_client import OllamaClient
from twitter_agent.models.schemas import Tweet, VoiceProfile
from twitter_agent.utils.analytics import AnalyticsProcessor


class VoiceAnalyzer:
    """Analyze Twitter user's voice and persona."""

    def __init__(
        self,
        twitter_client: TwitterAPIClient,
        ollama_client: OllamaClient,
        max_tweets: int = 100,
        prefer_cache_only: bool = False,
    ):
        """
        Initialize voice analyzer.

        Args:
            twitter_client: Twitter API client instance
            ollama_client: Ollama LLM client instance
            max_tweets: Maximum number of tweets to analyze
            prefer_cache_only: If True, only use cached tweets (don't fetch from API)
        """
        self.twitter_client = twitter_client
        self.ollama_client = ollama_client
        self.max_tweets = max_tweets
        self.prefer_cache_only = prefer_cache_only

    def analyze(self, username: str) -> VoiceProfile:
        """
        Analyze user's voice and persona.

        Args:
            username: Twitter username (without @)

        Returns:
            VoiceProfile object with analyzed characteristics
        """
        # Fetch user tweets
        if self.prefer_cache_only:
            logger.info(f"Using cached tweets only for @{username}...")
        else:
            logger.info(f"Fetching tweets for @{username}...")
        tweets = self.twitter_client.get_user_tweets(
            username, 
            max_results=self.max_tweets,
            prefer_cache_only=self.prefer_cache_only
        )

        if not tweets:
            raise ValueError(f"No tweets found for user @{username}")

        logger.info(f"Analyzing {len(tweets)} tweets...")

        # Extract tweet texts for LLM analysis
        tweet_texts = [tweet.text for tweet in tweets]

        # Use LLM to analyze voice
        logger.info("Using LLM to analyze voice and persona...")
        analysis_text = self.ollama_client.analyze_voice(tweet_texts, username)

        # Process analytics
        analytics_processor = AnalyticsProcessor(tweets)
        engagement_patterns = analytics_processor.analyze_engagement_patterns()

        # Extract structured information from LLM analysis
        # Parse the analysis text to extract key components
        voice_profile = self._parse_analysis(analysis_text, username, tweets, engagement_patterns)

        return voice_profile

    def _parse_analysis(
        self,
        analysis_text: str,
        username: str,
        tweets: list[Tweet],
        engagement_patterns: dict,
    ) -> VoiceProfile:
        """
        Parse LLM analysis text into structured VoiceProfile.

        Args:
            analysis_text: Raw analysis text from LLM
            username: Twitter username
            tweets: List of tweets analyzed
            engagement_patterns: Engagement analytics data

        Returns:
            VoiceProfile object
        """
        # Extract writing style and tone from analysis
        writing_style = self._extract_section(analysis_text, ["writing style", "style"])
        tone = self._extract_section(analysis_text, ["tone", "voice tone"])

        # Extract common topics
        topics_text = self._extract_section(analysis_text, ["topics", "themes", "subjects"])
        common_topics = self._extract_list_items(topics_text)

        # Extract hashtag usage from actual tweets
        hashtag_usage = {}
        for tweet in tweets:
            words = tweet.text.split()
            for word in words:
                if word.startswith("#"):
                    hashtag = word.lower()
                    hashtag_usage[hashtag] = hashtag_usage.get(hashtag, 0) + 1

        # Calculate average tweet length
        avg_length = (
            sum(len(tweet.text) for tweet in tweets) / len(tweets) if tweets else None
        )

        return VoiceProfile(
            username=username,
            writing_style=writing_style or "Analyzed from tweets",
            tone=tone or "Analyzed from tweets",
            common_topics=common_topics[:10],  # Top 10 topics
            hashtag_usage=hashtag_usage,
            average_tweet_length=int(avg_length) if avg_length else None,
            engagement_patterns=engagement_patterns,
        )

    @staticmethod
    def _extract_section(text: str, keywords: list[str]) -> str:
        """Extract a section from analysis text based on keywords."""
        text_lower = text.lower()
        for keyword in keywords:
            idx = text_lower.find(keyword)
            if idx != -1:
                # Find the section after the keyword
                start = idx + len(keyword)
                # Look for next colon or newline
                end = min(
                    text.find("\n", start) if text.find("\n", start) != -1 else len(text),
                    text.find(":", start) + 200 if text.find(":", start) != -1 else len(text),
                )
                section = text[start:end].strip()
                # Clean up
                section = section.lstrip(": -").strip()
                # Take first sentence or first 200 chars
                period_idx = section.find(".")
                if period_idx != -1 and period_idx < 200:
                    return section[: period_idx + 1]
                return section[:200]
        return ""

    @staticmethod
    def _extract_list_items(text: str) -> list[str]:
        """Extract list items from text (bulleted or numbered)."""
        items = []
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            # Skip empty lines
            if not line:
                continue
            # Check for bullet points or numbered items
            if line.startswith("- ") or line.startswith("* "):
                items.append(line[2:].strip())
            elif line[0].isdigit() and (line[1:3] == ". " or line[1:2] == ")"):
                items.append(line[3 if line[1:3] == ". " else 2 :].strip())
            # Also check for comma-separated items
            elif "," in line and len(items) == 0:
                items.extend([item.strip() for item in line.split(",")])
        return items[:10]  # Limit to 10 items

