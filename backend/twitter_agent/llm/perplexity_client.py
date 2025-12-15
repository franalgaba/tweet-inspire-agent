"""Perplexity API client for fetching topic information using the official SDK."""

import os
from dataclasses import dataclass
from typing import Callable, Optional

from loguru import logger

# Import Perplexity SDK with graceful fallback
try:
    from perplexity import Perplexity

    # Try to import error classes, but they may not exist in all SDK versions
    try:
        from perplexity.errors import (  # type: ignore
            APIStatusError,
            BadRequestError,
            RateLimitError,
        )
    except (ImportError, AttributeError):
        # If errors module doesn't exist, use generic exceptions
        APIStatusError = Exception
        BadRequestError = Exception
        RateLimitError = Exception
except ImportError:
    Perplexity = None
    APIStatusError = Exception
    BadRequestError = Exception
    RateLimitError = Exception


class PerplexityError(Exception):
    """Custom exception for Perplexity API errors."""

    pass


@dataclass
class ResearchConfig:
    """Configuration for research requests."""

    topic: str
    original_tweet_text: Optional[str] = None
    model: str = "sonar-pro"
    max_tokens: int = 800
    search_recency_filter: Optional[str] = "month"
    search_domain_filter: Optional[list[str]] = None


class PerplexityClient:
    """Client for interacting with Perplexity API using the official SDK."""

    # Model constants
    MODEL_SONAR_PRO = "sonar-pro"
    MODEL_SONAR_DEEP_RESEARCH = "sonar-deep-research"
    MODEL_SONAR_REASONING_PRO = "sonar-reasoning-pro"

    # Default configuration constants
    DEFAULT_MODEL = MODEL_SONAR_PRO
    DEFAULT_MAX_TOKENS = 800
    DEFAULT_DEEP_RESEARCH_MAX_TOKENS = 2000
    DEFAULT_TEMPERATURE = 0.3
    DEFAULT_SEARCH_RECENCY = "month"

    # Content detection thresholds
    FULL_CONTENT_MIN_LENGTH = 500
    FULL_CONTENT_MARKER = "\n\n"

    # System prompt for research assistant
    SYSTEM_PROMPT = (
        "You are an expert research assistant specializing in providing rich, "
        "nuanced context for social media content creation. Your research helps "
        "users understand topics deeply enough to craft engaging, informed responses. "
        "You provide balanced perspectives, highlight interesting angles, and note "
        "what makes topics conversation-worthy."
    )

    # Shared research requirements template
    RESEARCH_REQUIREMENTS_DEEP = (
        "1. Key facts and current information about the topic\n"
        "2. Multiple perspectives and viewpoints (pro/con, different schools of thought)\n"
        "3. Recent developments, trends, and controversies\n"
        "4. Implications and consequences\n"
        "5. Interesting angles and discussion points\n"
        "6. Cultural, industry, and social context\n"
        "7. Expert insights and analysis"
    )

    RESEARCH_REQUIREMENTS_STANDARD = (
        "1. Key facts and current information about the topic\n"
        "2. Different perspectives or viewpoints (pro/con, different schools of thought)\n"
        "3. Recent developments or controversies if relevant\n"
        "4. Interesting angles or discussion points that make this topic engaging\n"
        "5. Any cultural or industry context that's relevant"
    )

    # Perspective guidance mapping
    PERSPECTIVE_GUIDANCE = {
        "analytical": "\nFocus on analytical depth, implications, and deeper insights. Provide structured analysis.",
        "current": "\nFocus on recent developments, current trends, and real-time information. Emphasize what's happening now.",
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Perplexity API client.

        Args:
            api_key: Perplexity API key. If not provided, will try to get from env.

        Raises:
            ImportError: If Perplexity SDK is not installed
            ValueError: If API key is not provided
        """
        self._validate_sdk_available()
        self.api_key = self._get_api_key(api_key)
        self.client = Perplexity(api_key=self.api_key)

    @staticmethod
    def _validate_sdk_available() -> None:
        """Validate that Perplexity SDK is installed."""
        if Perplexity is None:
            raise ImportError(
                "Perplexity SDK not installed. Install it with: uv add perplexityai"
            )

    @staticmethod
    def _get_api_key(api_key: Optional[str]) -> str:
        """
        Get API key from parameter or environment variable.

        Args:
            api_key: Optional API key parameter

        Returns:
            API key string

        Raises:
            ValueError: If no API key is found
        """
        resolved_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        if not resolved_key:
            raise ValueError(
                "Perplexity API key is required. "
                "Set PERPLEXITY_API_KEY environment variable or pass api_key parameter."
            )
        return resolved_key

    def deep_research_topic(
        self,
        topic: str,
        original_tweet_text: Optional[str] = None,
        max_tokens: int = DEFAULT_DEEP_RESEARCH_MAX_TOKENS,
        search_recency_filter: Optional[str] = DEFAULT_SEARCH_RECENCY,
        search_domain_filter: Optional[list[str]] = None,
    ) -> str:
        """
        Perform deep research using Perplexity's specialized deep research models.

        This method uses:
        - sonar-deep-research: Exhaustive research across hundreds of sources with expert-level insights
        - sonar-reasoning-pro: Advanced reasoning for synthesizing and analyzing research

        According to Perplexity docs, sonar-deep-research conducts exhaustive searches,
        synthesizes expert-level insights, and generates detailed reports automatically.

        Args:
            topic: Topic or query to research
            original_tweet_text: Optional original tweet text for better context
            max_tokens: Maximum tokens in response (default: 2000 for deeper research)
            search_recency_filter: Filter search results by recency (default: "month")
            search_domain_filter: Filter search results by domain (list of trusted domains)

        Returns:
            Comprehensive research text with expert-level insights and analysis

        Raises:
            PerplexityError: If API request fails
        """
        logger.info(
            f"Performing deep research on topic: {topic[:100]}... using {self.MODEL_SONAR_DEEP_RESEARCH}"
        )

        config = ResearchConfig(
            topic=topic,
            original_tweet_text=original_tweet_text,
            max_tokens=max_tokens,
            search_recency_filter=search_recency_filter,
            search_domain_filter=search_domain_filter,
        )

        try:
            # Step 1: Conduct exhaustive research with sonar-deep-research
            deep_research_content = self._execute_research(
                config, self.MODEL_SONAR_DEEP_RESEARCH, self._build_deep_research_prompt
            )

            # Step 2: Synthesize with sonar-reasoning-pro for social media optimization
            return self._synthesize_for_social_media(config, deep_research_content)

        except Exception as e:
            # Fallback to standard research if deep research fails
            logger.warning(
                f"{self.MODEL_SONAR_DEEP_RESEARCH} failed, falling back to standard research: {e}"
            )
            return self._fallback_to_standard_research(config)

    def search_topic(
        self,
        topic: str,
        original_tweet_text: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        search_recency_filter: Optional[str] = DEFAULT_SEARCH_RECENCY,
        search_domain_filter: Optional[list[str]] = None,
    ) -> str:
        """
        Research a topic using Perplexity API with context-aware, comprehensive information.

        Args:
            topic: Topic or query to research
            original_tweet_text: Optional original tweet text for better context
            model: Model to use (default: sonar-pro)
            max_tokens: Maximum tokens in response (default: 800)
            search_recency_filter: Filter search results by recency (default: "month")
            search_domain_filter: Filter search results by domain (list of trusted domains)

        Returns:
            Rich context text about the topic with multiple perspectives and discussion points

        Raises:
            PerplexityError: If API request fails
        """
        model_name = model or self.DEFAULT_MODEL
        logger.info(f"Researching topic: {topic[:100]}... (model: {model_name})")

        config = ResearchConfig(
            topic=topic,
            original_tweet_text=original_tweet_text,
            model=model_name,
            max_tokens=max_tokens,
            search_recency_filter=search_recency_filter,
            search_domain_filter=search_domain_filter,
        )

        try:
            return self._execute_research(
                config, model_name, self._build_research_prompt
            )
        except Exception as e:
            self._handle_error(e)

    def _execute_research(
        self,
        config: ResearchConfig,
        model: str,
        prompt_builder: Callable[[str, Optional[str]], str],
    ) -> str:
        """
        Execute a research request with the given configuration.

        Args:
            config: Research configuration
            model: Model to use for the research
            prompt_builder: Function to build the research prompt

        Returns:
            Extracted research content

        Raises:
            PerplexityError: If API request fails
        """
        web_search_options = self._build_web_search_options(
            config.search_recency_filter, config.search_domain_filter
        )
        research_prompt = prompt_builder(config.topic, config.original_tweet_text)
        completion = self._call_api(
            research_prompt, model, config.max_tokens, web_search_options
        )
        return self._extract_content(completion, config.topic)

    def _synthesize_for_social_media(
        self, config: ResearchConfig, research_content: str
    ) -> str:
        """
        Synthesize research content for social media using sonar-reasoning-pro.

        Args:
            config: Research configuration
            research_content: Raw research content to synthesize

        Returns:
            Synthesized content optimized for social media

        Raises:
            PerplexityError: If synthesis fails (falls back to original content)
        """
        try:
            logger.debug(
                f"Analyzing research with {self.MODEL_SONAR_REASONING_PRO} (synthesis)..."
            )
            reasoning_prompt = self._build_synthesis_prompt(
                config.topic, research_content
            )
            web_search_options = self._build_web_search_options(
                config.search_recency_filter, config.search_domain_filter
            )

            completion = self._call_api(
                reasoning_prompt,
                self.MODEL_SONAR_REASONING_PRO,
                config.max_tokens,
                web_search_options,
            )
            return self._extract_content(completion, config.topic)
        except Exception as e:
            # Fallback to original research content if synthesis fails
            logger.warning(
                f"{self.MODEL_SONAR_REASONING_PRO} not available, "
                f"using {self.MODEL_SONAR_DEEP_RESEARCH} output directly: {e}"
            )
            return research_content

    def _fallback_to_standard_research(self, config: ResearchConfig) -> str:
        """
        Fallback to standard research when deep research fails.

        Args:
            config: Research configuration

        Returns:
            Research content from standard research
        """
        return self.search_topic(
            topic=config.topic,
            original_tweet_text=config.original_tweet_text,
            max_tokens=config.max_tokens,
            search_recency_filter=config.search_recency_filter,
            search_domain_filter=config.search_domain_filter,
        )

    def _build_web_search_options(
        self,
        search_recency_filter: Optional[str],
        search_domain_filter: Optional[list[str]],
    ) -> dict:
        """
        Build web search options dictionary.

        Args:
            search_recency_filter: Optional recency filter
            search_domain_filter: Optional domain filter

        Returns:
            Dictionary of web search options (empty dict if no filters)
        """
        options = {}
        if search_recency_filter:
            options["search_recency_filter"] = search_recency_filter
        if search_domain_filter:
            options["search_domain_filter"] = search_domain_filter
        return options

    @classmethod
    def _is_full_content(cls, topic: str) -> bool:
        """
        Determine if topic is full content or a summary.

        Args:
            topic: Topic string to check

        Returns:
            True if topic appears to be full content, False if summary
        """
        return (
            len(topic) > cls.FULL_CONTENT_MIN_LENGTH or cls.FULL_CONTENT_MARKER in topic
        )

    @classmethod
    def _build_deep_research_prompt(
        cls, topic: str, original_tweet_text: Optional[str]
    ) -> str:
        """
        Build comprehensive research prompt for sonar-deep-research model.

        Args:
            topic: Topic to research (can be a short summary or full content)
            original_tweet_text: Optional original tweet text for context
                (Note: if topic is full content, this should be None)

        Returns:
            Formatted research prompt string optimized for deep research
        """
        is_full_content = cls._is_full_content(topic)

        if is_full_content:
            # Topic is full content - treat it as the complete context
            base_prompt = f"""Conduct comprehensive research based on this content:

{topic}

Analyze this content thoroughly and provide exhaustive research that includes:
{cls.RESEARCH_REQUIREMENTS_DEEP}

CRITICAL: Stay focused on the topics and themes present in the content above - explore different facets, implications, and perspectives WITHIN these topic areas, not unrelated topics.

Format as comprehensive research (8-12 sentences) that enables crafting distinctive, value-added social media content with deep context."""
        else:
            # Topic is a summary - use traditional approach
            base_prompt = f"""Conduct comprehensive research on: "{topic}"

Provide exhaustive research that includes:
{cls.RESEARCH_REQUIREMENTS_DEEP}

CRITICAL: Stay focused on "{topic}" - explore different facets, implications, and perspectives WITHIN this topic area, not unrelated topics.

Format as comprehensive research (8-12 sentences) that enables crafting distinctive, value-added social media content with deep context."""

        if original_tweet_text:
            return f"""{base_prompt}

Additional context: This research is for crafting a unique Twitter response to this tweet: "{original_tweet_text}\""""

        return base_prompt

    @classmethod
    def _build_synthesis_prompt(cls, topic: str, research_content: str) -> str:
        """
        Build prompt for synthesizing research content for social media.

        Args:
            topic: Research topic
            research_content: Comprehensive research content to synthesize

        Returns:
            Formatted synthesis prompt
        """
        return f"""Analyze and synthesize this comprehensive research about "{topic}" for social media content creation:

{research_content}

Provide a focused, nuanced summary (5-8 sentences) that:
- Extracts the most relevant insights for engaging social media content
- Highlights different perspectives and angles
- Identifies discussion-worthy points and implications
- Presents information in a way that enables crafting unique, value-added responses
- Maintains focus on the core topic while providing depth

Format as rich context suitable for generating engaging Twitter content."""

    @classmethod
    def _build_research_prompt(
        cls,
        topic: str,
        original_tweet_text: Optional[str],
        perspective: Optional[str] = None,
    ) -> str:
        """
        Build research prompt with optional tweet context and perspective.

        Args:
            topic: Topic to research
            original_tweet_text: Optional original tweet text for context
            perspective: Optional perspective type ("analytical", "current", etc.)

        Returns:
            Formatted research prompt string
        """
        perspective_guidance = cls._get_perspective_guidance(perspective)

        if original_tweet_text:
            return f"""Research this topic: "{topic}"

Original tweet says: "{original_tweet_text}"

Provide rich context about THIS SPECIFIC TOPIC that helps craft a UNIQUE Twitter response. Stay on the same topic but provide:
- Different angles, nuances, or deeper insights about the SAME topic
- Additional context, examples, or implications within this topic area
- Related aspects or perspectives on this topic that weren't mentioned
- Recent developments or debates specifically about this topic

CRITICAL: Stay focused on "{topic}" - do not branch into unrelated topics. Explore different facets, implications, or perspectives WITHIN this topic area.

Include:
{cls.RESEARCH_REQUIREMENTS_STANDARD}
{perspective_guidance}

IMPORTANT: Provide deeper context about this specific topic to enable unique responses that add value while staying on-topic.

Format as rich context (3-5 sentences) about this topic that enables crafting distinctive, value-added responses."""

        return f"""Research this topic: "{topic}"

Provide comprehensive context that would help someone craft an engaging Twitter post about this topic. Include:
{cls.RESEARCH_REQUIREMENTS_STANDARD}
{perspective_guidance}

Format your response as rich context (3-5 sentences) that captures the essence and interesting aspects of this topic."""

    @classmethod
    def _get_perspective_guidance(cls, perspective: Optional[str]) -> str:
        """
        Get perspective-specific guidance text.

        Args:
            perspective: Perspective type ("analytical", "current", etc.)

        Returns:
            Perspective guidance text (empty string if no perspective)
        """
        return cls.PERSPECTIVE_GUIDANCE.get(perspective, "")

    def _call_api(
        self,
        research_prompt: str,
        model: str,
        max_tokens: int,
        web_search_options: dict,
    ):
        """
        Call Perplexity API with the research prompt.

        Args:
            research_prompt: The research prompt to send
            model: Model to use
            max_tokens: Maximum tokens in response
            web_search_options: Web search options dictionary

        Returns:
            API completion response

        Raises:
            PerplexityError: If API call fails
        """
        # Only include web_search_options if it has values
        api_options = web_search_options if web_search_options else None

        return self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": research_prompt},
            ],
            model=model,
            temperature=self.DEFAULT_TEMPERATURE,
            max_tokens=max_tokens,
            web_search_options=api_options,
        )

    @staticmethod
    def _extract_content(completion, fallback_topic: str) -> str:
        """
        Extract content from API completion response.

        Args:
            completion: API completion response object
            fallback_topic: Topic to use if no content is found

        Returns:
            Extracted content string
        """
        if not completion.choices:
            logger.warning("No content in Perplexity response")
            return f"Topic: {fallback_topic}"

        content = completion.choices[0].message.content
        logger.debug(f"Perplexity research received: {len(content)} characters")
        logger.debug(f"Research content preview: {content[:200]}...")
        return content

    def _handle_error(self, error: Exception) -> None:
        """
        Handle API errors and convert to PerplexityError.

        Args:
            error: The exception that occurred

        Raises:
            PerplexityError: Always raises with appropriate error message
        """
        error_msg = str(error)
        error_type = type(error).__name__
        status_code = getattr(error, "status_code", None)

        # Check for rate limit errors
        if "rate limit" in error_msg.lower() or error_type == "RateLimitError":
            self._raise_rate_limit_error(error_msg, error)
        # Check for bad request errors
        elif status_code == 400:
            self._raise_bad_request_error(error_msg, error)
        # Check for other API errors
        elif status_code:
            self._raise_api_error(status_code, error_msg, error)
        # Fallback for unexpected errors
        else:
            logger.exception(f"Unexpected error calling Perplexity API: {error_msg}")
            raise PerplexityError(f"Unexpected error: {error_msg}") from error

    @staticmethod
    def _raise_rate_limit_error(error_msg: str, error: Exception) -> None:
        """Raise rate limit error."""
        logger.error(f"Perplexity API rate limit exceeded: {error_msg}")
        raise PerplexityError(
            f"Rate limit exceeded. Please retry later: {error_msg}"
        ) from error

    @staticmethod
    def _raise_bad_request_error(error_msg: str, error: Exception) -> None:
        """Raise bad request error."""
        logger.error(f"Perplexity API bad request: {error_msg}")
        raise PerplexityError(f"Invalid request parameters: {error_msg}") from error

    @staticmethod
    def _raise_api_error(status_code: int, error_msg: str, error: Exception) -> None:
        """Raise generic API error."""
        logger.error(f"Perplexity API error ({status_code}): {error_msg}")
        raise PerplexityError(
            f"Perplexity API error ({status_code}): {error_msg}"
        ) from error

    def close(self):
        """Close the client (SDK handles this automatically, but kept for compatibility)."""
        # The SDK client doesn't need explicit closing, but we keep this for compatibility
        pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
