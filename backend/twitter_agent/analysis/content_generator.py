"""Content generator for creating tweet proposals."""

from typing import Optional

from loguru import logger

from twitter_agent.llm.ollama_client import OllamaClient
from twitter_agent.models.schemas import ContentProposal, ContentType, VoiceProfile
from twitter_agent.utils.analytics import AnalyticsProcessor
from twitter_agent.utils.calendar import CalendarProcessor
from twitter_agent.utils.file_processor import FileProcessor


class ContentGenerator:
    """Generate Twitter content proposals."""

    def __init__(
        self,
        ollama_client: OllamaClient,
        voice_profile: VoiceProfile,
        file_processor: Optional[FileProcessor] = None,
        analytics_processor: Optional[AnalyticsProcessor] = None,
        calendar_processor: Optional[CalendarProcessor] = None,
    ):
        """
        Initialize content generator.

        Args:
            ollama_client: Ollama LLM client
            voice_profile: Analyzed voice profile
            file_processor: Optional file processor for content context
            analytics_processor: Optional analytics processor for insights
            calendar_processor: Optional calendar processor for scheduling
        """
        self.ollama_client = ollama_client
        self.voice_profile = voice_profile
        self.file_processor = file_processor
        self.analytics_processor = analytics_processor
        self.calendar_processor = calendar_processor

    def generate(
        self,
        content_type: ContentType = ContentType.TWEET,
        use_content: bool = True,
        use_analytics: bool = True,
        use_calendar: bool = True,
        count: int = 1,
        topic: Optional[str] = None,
        original_tweet_context: Optional[str] = None,
        thread_count: int = 5,
        vibe: Optional[str] = None,
    ) -> list[ContentProposal]:
        """
        Generate content proposals.

        Args:
            content_type: Type of content to generate
            use_content: Whether to use content from files
            use_analytics: Whether to use analytics insights
            use_calendar: Whether to use calendar hints
            count: Number of proposals to generate
            topic: Optional topic or text to generate tweet about
            original_tweet_context: Optional context of original tweet (for replies/quotes)
            thread_count: Number of tweets in a thread (only used when content_type is THREAD)
            vibe: Optional vibe/mood description for the generated content (e.g., "positive and excited", "skeptical")

        Returns:
            List of ContentProposal objects
        """
        topic_info = f", topic: {topic}" if topic else ""
        logger.info(
            f"Generating {count} {content_type.value} proposal(s) "
            f"(content: {use_content}, analytics: {use_analytics}, calendar: {use_calendar}{topic_info})"
        )
        proposals = []

        # Prepare context
        content_context = None
        if use_content and self.file_processor:
            content_context = self.file_processor.get_content_summary()
            logger.debug(f"Loaded content context: {len(content_context)} characters")

        analytics_insights = None
        if use_analytics and self.analytics_processor:
            analytics_insights = self.analytics_processor.get_insights_summary()
            logger.debug("Analytics insights loaded")

        calendar_hints = None
        if use_calendar and self.calendar_processor:
            calendar_hints = self.calendar_processor.generate_schedule_hints()
            logger.debug("Calendar hints loaded")

        # Generate voice analysis summary
        voice_summary = self._format_voice_profile()

        # Generate proposals
        for i in range(count):
            logger.debug(f"Generating proposal {i+1}/{count}")
            # Generate content using LLM
            generated_text = self.ollama_client.generate_content(
                voice_analysis=voice_summary,
                content_context=content_context,
                content_type=content_type.value,
                analytics_insights=analytics_insights,
                calendar_hints=calendar_hints,
                topic=topic,
                original_tweet_context=original_tweet_context,
                thread_count=thread_count if content_type == ContentType.THREAD else None,
                vibe=vibe,
            )

            # Parse generated content (handle threads)
            content = self._parse_generated_content(generated_text, content_type)

            # Determine suggested date from calendar
            suggested_date = None
            if use_calendar and self.calendar_processor:
                suggested_dates = self.calendar_processor.suggest_content_dates(count=count)
                if i < len(suggested_dates):
                    suggested_date = suggested_dates[i]

            # Build rationale
            based_on = []
            if use_content:
                based_on.append("content")
            if use_analytics:
                based_on.append("analytics")
            if use_calendar:
                based_on.append("calendar")

            proposal = ContentProposal(
                content_type=content_type,
                content=content,
                suggested_date=suggested_date,
                rationale=f"Generated based on voice analysis and {', '.join(based_on)}",
                based_on=based_on,
            )

            proposals.append(proposal)

        return proposals

    def _format_voice_profile(self) -> str:
        """Format voice profile for LLM prompt."""
        parts = []
        parts.append(f"USER: @{self.voice_profile.username}")
        parts.append(f"WRITING STYLE: {self.voice_profile.writing_style}")
        parts.append(f"TONE: {self.voice_profile.tone}")
        
        # Note capitalization patterns
        if "lowercase" in self.voice_profile.writing_style.lower() or "casual" in self.voice_profile.writing_style.lower():
            parts.append("CAPITALIZATION: Primarily lowercase/sentence case")
        else:
            parts.append("CAPITALIZATION: Standard capitalization (observe their patterns)")
        
        if self.voice_profile.common_topics:
            topics_str = ", ".join(self.voice_profile.common_topics)
            parts.append(f"COMMON TOPICS: {topics_str}")
        if self.voice_profile.average_tweet_length:
            parts.append(f"AVERAGE TWEET LENGTH: {self.voice_profile.average_tweet_length} characters")
        
        # Hashtag usage - note if they rarely use them
        if self.voice_profile.hashtag_usage:
            total_hashtags = sum(self.voice_profile.hashtag_usage.values())
            if total_hashtags < 5:  # Very few hashtags used
                parts.append("HASHTAG USAGE: Rarely uses hashtags - DO NOT include hashtags in generated content")
            else:
                top_hashtags = sorted(
                    self.voice_profile.hashtag_usage.items(), key=lambda x: x[1], reverse=True
                )[:5]
                hashtags_str = ", ".join([tag for tag, _ in top_hashtags])
                parts.append(f"COMMON HASHTAGS: {hashtags_str} (use sparingly, only if user frequently uses them)")
        else:
            parts.append("HASHTAG USAGE: Does not use hashtags - DO NOT include hashtags")

        return "\n".join(parts)

    def _parse_generated_content(
        self, generated_text: str, content_type: ContentType
    ) -> str | list[str]:
        """
        Parse generated content based on type.

        Args:
            generated_text: Raw generated text from LLM
            content_type: Type of content expected

        Returns:
            String for single tweet, list of strings for thread
        """
        if content_type == ContentType.THREAD:
            # Parse thread format (1/N, 2/N, etc.)
            lines = generated_text.split("\n")
            tweets = []
            current_tweet = []

            for line in lines:
                line = line.strip()
                if not line:
                    if current_tweet:
                        tweets.append(" ".join(current_tweet).strip())
                        current_tweet = []
                    continue

                # Check for thread markers (1/N, 2/N, etc.) - more flexible matching
                if line and line[0].isdigit():
                    # Look for patterns like "1/5", "1)", "1.", etc.
                    marker_patterns = ["/", ")", "."]
                    has_marker = any(pattern in line[:6] for pattern in marker_patterns)
                    
                    if has_marker:
                        if current_tweet:
                            tweets.append(" ".join(current_tweet).strip())
                        # Extract tweet text after marker
                        # Find the end of the marker (space, colon, or end of marker pattern)
                        marker_end = len(line)
                        for i, char in enumerate(line):
                            if i > 0 and (char == " " or char == ":" or char == "-"):
                                marker_end = i + 1
                                break
                        tweet_text = line[marker_end:].strip()
                        if tweet_text:
                            current_tweet = [tweet_text]
                        else:
                            current_tweet = []
                    else:
                        current_tweet.append(line)
                else:
                    current_tweet.append(line)

            if current_tweet:
                tweets.append(" ".join(current_tweet).strip())

            # Clean up tweets - remove empty ones
            tweets = [t for t in tweets if t]

            # If parsing failed or got too few tweets, try smarter splitting
            if len(tweets) < 2:
                # Try splitting by double newlines first
                paragraphs = [p.strip() for p in generated_text.split("\n\n") if p.strip()]
                if len(paragraphs) > 1:
                    tweets = paragraphs
                else:
                    # If still one block, try to intelligently split long text
                    text = generated_text.strip()
                    if len(text) > 400:
                        # Try to split at sentence boundaries, ~280 chars per tweet
                        sentences = text.replace(". ", ".\n").split("\n")
                        chunks = []
                        current_chunk = []
                        current_length = 0
                        
                        for sentence in sentences:
                            sentence = sentence.strip()
                            if not sentence:
                                continue
                            sentence_length = len(sentence) + 1  # +1 for space
                            
                            if current_length + sentence_length > 260 and current_chunk:
                                chunks.append(" ".join(current_chunk))
                                current_chunk = [sentence]
                                current_length = len(sentence)
                            else:
                                current_chunk.append(sentence)
                                current_length += sentence_length
                        
                        if current_chunk:
                            chunks.append(" ".join(current_chunk))
                        
                        if chunks:
                            tweets = chunks[:10]  # Limit to reasonable number

            # Final fallback - if still nothing, return as single tweet
            if not tweets:
                tweets = [generated_text.strip()]

            return tweets
        else:
            # Single tweet - clean up and return
            text = generated_text.strip()
            # Remove any numbering or markers
            lines = text.split("\n")
            if len(lines) > 1:
                # Take first substantial line
                for line in lines:
                    line = line.strip()
                    if line and not line[0].isdigit():
                        return line
            return text

