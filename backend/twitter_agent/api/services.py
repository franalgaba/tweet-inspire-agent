"""Service functions for web API - extracted from CLI logic."""

import json
import os
from pathlib import Path
from typing import Optional, Generator

from twitter_agent.analysis.content_generator import ContentGenerator
from twitter_agent.analysis.voice_analyzer import VoiceAnalyzer
from twitter_agent.clients.twitter import TwitterAPIClient
from twitter_agent.llm.ollama_client import OllamaClient
from twitter_agent.llm.perplexity_client import PerplexityClient, PerplexityError
from twitter_agent.models.schemas import ContentType, VoiceProfile
from twitter_agent.utils.analytics import AnalyticsProcessor
from twitter_agent.utils.calendar import CalendarProcessor
from twitter_agent.utils.file_processor import FileProcessor
from twitter_agent.utils.cache import TwitterCache
from twitter_agent.api.research_cache import get_research


def get_config() -> dict:
    """Get configuration from environment variables."""
    return {
        "twitter_api_key": os.getenv("TWITTER_API_KEY"),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "llama3.2"),
        "content_dir": os.getenv("CONTENT_DIR", "content"),
    }


def analyze_voice(
    username: str, max_tweets: int = 100, save_profile: bool = False
) -> tuple[dict, Optional[str]]:
    """
    Analyze a Twitter user's voice and persona.

    Returns:
        Tuple of (profile_dict, saved_path)
    """
    config = get_config()
    if not config["twitter_api_key"]:
        raise ValueError("TWITTER_API_KEY environment variable not set")

    twitter_client = None
    ollama_client = None

    try:
        # Initialize clients
        twitter_client = TwitterAPIClient(api_key=config["twitter_api_key"])
        ollama_client = OllamaClient(
            base_url=config["ollama_base_url"], model=config["ollama_model"]
        )

        # Analyze voice
        analyzer = VoiceAnalyzer(twitter_client, ollama_client, max_tweets=max_tweets)
        voice_profile = analyzer.analyze(username)

        # Convert to dict
        profile_dict = voice_profile.model_dump(mode="json")

        # Save to file if requested
        saved_path = None
        if save_profile:
            output_path = Path(config["content_dir"]) / f"{username}_profile.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(profile_dict, indent=2, default=str))
            saved_path = str(output_path)

        return profile_dict, saved_path

    finally:
        if twitter_client:
            twitter_client.close()
        if ollama_client:
            ollama_client.close()


def generate_content(
    username: str,
    content_type: str = "tweet",
    count: int = 1,
    content_dir: Optional[str] = None,
    calendar_file: Optional[str] = None,
    use_analytics: bool = True,
    use_calendar: bool = True,
    profile_file: Optional[str] = None,
    topic: Optional[str] = None,
    thread_count: int = 5,
) -> list[dict]:
    """
    Generate content proposals based on analyzed voice.

    Returns:
        List of proposal dictionaries
    """
    config = get_config()
    if not config["twitter_api_key"]:
        raise ValueError("TWITTER_API_KEY environment variable not set")

    # Parse content type
    try:
        content_type_enum = ContentType(content_type.lower())
    except ValueError:
        raise ValueError(
            f"Invalid content type '{content_type}'. Use: tweet, thread, reply, quote"
        )

    twitter_client = None
    ollama_client = None
    perplexity_client = None

    try:
        # Initialize clients
        twitter_client = TwitterAPIClient(api_key=config["twitter_api_key"])
        ollama_client = OllamaClient(
            base_url=config["ollama_base_url"], model=config["ollama_model"]
        )

        # Check Ollama availability
        if not ollama_client.check_available():
            raise ValueError(
                f"Ollama is not available at {config['ollama_base_url']}. "
                f"Make sure Ollama is running and model '{config['ollama_model']}' is installed."
            )

        # Load or analyze voice profile
        if profile_file:
            profile_path = Path(profile_file)
            if not profile_path.exists():
                raise FileNotFoundError(f"Profile file not found: {profile_file}")
            profile_data = json.loads(profile_path.read_text())
            voice_profile = VoiceProfile(**profile_data)
        else:
            # Use cached tweets only for generate command
            analyzer = VoiceAnalyzer(
                twitter_client, ollama_client, max_tweets=1000, prefer_cache_only=True
            )
            voice_profile = analyzer.analyze(username)

        # Initialize processors
        content_dir_path = content_dir or config["content_dir"]
        file_processor = FileProcessor(content_dir=content_dir_path)

        analytics_processor = None
        if use_analytics:
            # Use cached tweets only for generate command
            tweets = twitter_client.get_user_tweets(
                username, max_results=1000, prefer_cache_only=True
            )
            if tweets:
                analytics_processor = AnalyticsProcessor(tweets)

        calendar_processor = None
        if use_calendar and calendar_file:
            calendar_processor = CalendarProcessor(calendar_file=calendar_file)
            calendar_processor.load_calendar()

        # Fetch topic information from Perplexity if topic is provided
        topic_info = None
        if topic:
            try:
                perplexity_client = PerplexityClient()
                topic_info = perplexity_client.search_topic(topic)
            except ValueError:
                # PERPLEXITY_API_KEY not set, skip topic research
                pass
            except PerplexityError:
                # Failed to fetch topic information, continue without it
                pass

        # Generate content
        generator = ContentGenerator(
            ollama_client=ollama_client,
            voice_profile=voice_profile,
            file_processor=file_processor,
            analytics_processor=analytics_processor,
            calendar_processor=calendar_processor,
        )

        proposals = generator.generate(
            content_type=content_type_enum,
            use_content=True,
            use_analytics=use_analytics,
            use_calendar=use_calendar,
            count=count,
            topic=topic_info if topic_info else topic,
            thread_count=thread_count,
        )

        # Convert proposals to dicts
        return [proposal.model_dump(mode="json") for proposal in proposals]

    finally:
        if twitter_client:
            twitter_client.close()
        if ollama_client:
            ollama_client.close()
        if perplexity_client:
            perplexity_client.close()


def inspire_from_tweet(
    username: str,
    tweet_url: str,
    content_type: str = "all",
    profile_file: Optional[str] = None,
    thread_count: int = 5,
    vibe: Optional[str] = None,
    deep_research: bool = False,
    use_full_content: bool = False,
    context: Optional[str] = None,
) -> tuple[dict, dict, Optional[str]]:
    """
    Generate content inspired by a tweet URL.

    Returns:
        Tuple of (original_tweet_dict, proposals_dict)
    """
    config = get_config()
    if not config["twitter_api_key"]:
        raise ValueError("TWITTER_API_KEY environment variable not set")

    twitter_client = None
    ollama_client = None
    perplexity_client = None

    try:
        # Initialize clients
        twitter_client = TwitterAPIClient(api_key=config["twitter_api_key"])
        ollama_client = OllamaClient(
            base_url=config["ollama_base_url"], model=config["ollama_model"]
        )

        # Check Ollama availability
        try:
            ollama_client.client.get("/api/tags")
        except Exception:
            raise ValueError(
                f"Cannot connect to Ollama at {config['ollama_base_url']}. "
                f"Make sure Ollama is running and model '{config['ollama_model']}' is installed."
            )

        # Extract tweet ID from URL
        tweet_id = TwitterAPIClient.extract_tweet_id_from_url(tweet_url)
        if not tweet_id:
            raise ValueError(f"Could not extract tweet ID from URL: {tweet_url}")

        # Fetch the tweet
        original_tweet = twitter_client.get_tweet_by_id(tweet_id)

        # Check if tweet is part of a thread
        thread_tweets = None
        thread_content = None
        try:
            thread_tweets = twitter_client.get_thread_context(tweet_id)
            if thread_tweets and len(thread_tweets) > 1:
                thread_texts = [tweet.text for tweet in thread_tweets]
                thread_content = "\n\n".join(thread_texts)
        except Exception:
            pass

        # Check if tweet links to an article
        article_data = None
        article_content = None
        try:
            article_data = twitter_client.get_article_by_tweet_id(tweet_id)
            if article_data:
                article_content = article_data.get("full_text", "")
        except Exception:
            pass

        # Extract topic from the tweet
        topic_source = original_tweet.text
        if thread_content:
            topic_source = thread_content
            if article_content:
                topic_source = (
                    f"{thread_content}\n\nArticle content:\n{article_content[:2000]}"
                )
        elif article_content:
            topic_source = (
                f"{original_tweet.text}\n\nArticle content:\n{article_content[:2000]}"
            )

        # Extract topic summary
        extracted_topic = ollama_client.extract_topic(topic_source)

        # Research topic with Perplexity
        topic_info = None
        try:
            perplexity_client = PerplexityClient()
            research_context = thread_content if thread_content else original_tweet.text
            if article_content:
                research_context = f"{research_context}\n\nRelated article content:\n{article_content[:1500]}"

            if deep_research:
                if use_full_content:
                    topic_info = perplexity_client.deep_research_topic(
                        topic=topic_source, original_tweet_text=None
                    )
                else:
                    topic_info = perplexity_client.deep_research_topic(
                        topic=extracted_topic, original_tweet_text=research_context
                    )
            else:
                topic_info = perplexity_client.search_topic(
                    extracted_topic, original_tweet_text=research_context
                )
        except ValueError:
            # PERPLEXITY_API_KEY not set
            pass
        except PerplexityError:
            # Failed to fetch topic information
            pass

        # Load or analyze voice profile
        if profile_file:
            profile_path = Path(profile_file)
            if not profile_path.exists():
                raise FileNotFoundError(f"Profile file not found: {profile_file}")
            profile_data = json.loads(profile_path.read_text())
            voice_profile = VoiceProfile(**profile_data)
        else:
            analyzer = VoiceAnalyzer(
                twitter_client, ollama_client, max_tweets=1000, prefer_cache_only=True
            )
            voice_profile = analyzer.analyze(username)

        # Use researched topic info if available, otherwise use extracted topic
        final_topic = topic_info if topic_info else extracted_topic

        # Build context including thread and article if available
        if thread_content:
            original_tweet_context = f"Thread by @{original_tweet.author_username} ({len(thread_tweets)} tweets):\n{thread_content}"
        else:
            original_tweet_context = f"Original tweet by @{original_tweet.author_username}:\n{original_tweet.text}"

        if article_content:
            original_tweet_context += (
                f"\n\nArticle linked in tweet:\n{article_content[:2000]}"
            )

        # Add user-provided context if given
        if context:
            original_tweet_context += f"\n\nAdditional context:\n{context}"

        # Store research for potential regeneration
        from twitter_agent.api.research_cache import store_research

        research_id = store_research(
            username=username,
            tweet_url=tweet_url,
            original_tweet=original_tweet.model_dump(mode="json"),
            topic_info=topic_info,
            extracted_topic=extracted_topic,
            original_tweet_context=original_tweet_context,
            voice_profile=voice_profile.model_dump(mode="json"),
            thread_content=thread_content,
            article_content=article_content,
        )

        # Parse content type
        generate_all = content_type.lower() == "all"
        if not generate_all:
            try:
                requested_type = ContentType(content_type.lower())
            except ValueError:
                raise ValueError(
                    f"Invalid content type '{content_type}'. Use: tweet, thread, reply, quote, or all"
                )

        # Generate content
        generator = ContentGenerator(
            ollama_client=ollama_client,
            voice_profile=voice_profile,
            file_processor=None,
            analytics_processor=None,
            calendar_processor=None,
        )

        qt_proposals = []
        tweet_proposals = []
        reply_proposals = []
        thread_proposals = []

        if generate_all or content_type.lower() == "quote":
            qt_proposals = generator.generate(
                content_type=ContentType.QUOTE,
                use_content=False,
                use_analytics=False,
                use_calendar=False,
                count=1,
                topic=final_topic,
                original_tweet_context=original_tweet_context,
                vibe=vibe,
            )

        if generate_all or content_type.lower() == "tweet":
            tweet_proposals = generator.generate(
                content_type=ContentType.TWEET,
                use_content=False,
                use_analytics=False,
                use_calendar=False,
                count=1,
                topic=final_topic,
                original_tweet_context=None,
                vibe=vibe,
            )

        if generate_all or content_type.lower() == "reply":
            reply_proposals = generator.generate(
                content_type=ContentType.REPLY,
                use_content=False,
                use_analytics=False,
                use_calendar=False,
                count=1,
                topic=final_topic,
                original_tweet_context=original_tweet_context,
                vibe=vibe,
            )

        if content_type.lower() == "thread":
            thread_proposals = generator.generate(
                content_type=ContentType.THREAD,
                use_content=False,
                use_analytics=False,
                use_calendar=False,
                count=1,
                topic=final_topic,
                original_tweet_context=None,
                thread_count=thread_count,
                vibe=vibe,
            )

        # Convert to dicts
        original_tweet_dict = original_tweet.model_dump(mode="json")
        proposals_dict = {
            "quote": [p.model_dump(mode="json") for p in qt_proposals],
            "tweet": [p.model_dump(mode="json") for p in tweet_proposals],
            "reply": [p.model_dump(mode="json") for p in reply_proposals],
            "thread": [p.model_dump(mode="json") for p in thread_proposals],
        }

        return original_tweet_dict, proposals_dict, research_id

    finally:
        if twitter_client:
            twitter_client.close()
        if ollama_client:
            ollama_client.close()
        if perplexity_client:
            perplexity_client.close()


def inspire_from_tweet_with_progress(
    username: str,
    tweet_url: str,
    content_type: str = "all",
    profile_file: Optional[str] = None,
    thread_count: int = 5,
    vibe: Optional[str] = None,
    deep_research: bool = False,
    use_full_content: bool = False,
    context: Optional[str] = None,
) -> Generator[dict, None, None]:
    """
    Generate content inspired by a tweet URL with progress updates.

    Yields progress events as dictionaries with 'step', 'message', and optionally 'progress' (0-100).
    Final event has step='complete' with 'data' containing the full result.

    If no cache exists for the user, automatically fetches tweets first.
    """
    config = get_config()
    if not config["twitter_api_key"]:
        raise ValueError("TWITTER_API_KEY environment variable not set")

    twitter_client = None
    ollama_client = None
    perplexity_client = None

    try:
        # Step 1: Initialize clients
        yield {
            "step": "initializing",
            "message": "Initializing services...",
            "progress": 5,
        }

        twitter_client = TwitterAPIClient(api_key=config["twitter_api_key"])
        ollama_client = OllamaClient(
            base_url=config["ollama_base_url"], model=config["ollama_model"]
        )

        # Check Ollama availability
        try:
            ollama_client.client.get("/api/tags")
        except Exception:
            raise ValueError(
                f"Cannot connect to Ollama at {config['ollama_base_url']}. "
                f"Make sure Ollama is running and model '{config['ollama_model']}' is installed."
            )

        # Step 2: Check cache for user and fetch tweets if needed
        yield {
            "step": "checking_cache",
            "message": f"Checking cache for @{username}...",
            "progress": 10,
        }

        # Try to get cached tweets first (this respects TTL expiry)
        cached_tweets = None
        if not profile_file:
            cached_tweets = twitter_client.get_user_tweets(
                username, max_results=200, prefer_cache_only=True
            )

        # Step 3: Fetch tweets if not cached or cache is expired
        if not cached_tweets and not profile_file:
            yield {
                "step": "fetching_tweets",
                "message": f"Fetching tweets for @{username}...",
                "progress": 15,
            }

            # This will fetch and cache the tweets
            tweets = twitter_client.get_user_tweets(
                username, max_results=200, prefer_cache_only=False
            )
            if not tweets:
                raise ValueError(
                    f"Could not fetch tweets for @{username}. User may not exist or have no tweets."
                )

            yield {
                "step": "fetching_tweets",
                "message": f"Fetched {len(tweets)} tweets for @{username}",
                "progress": 20,
            }
        else:
            yield {
                "step": "checking_cache",
                "message": f"Using cached data for @{username}",
                "progress": 15,
            }

        # Step 4: Extract tweet ID and fetch original tweet
        yield {
            "step": "fetching_tweet",
            "message": "Fetching the original tweet...",
            "progress": 25,
        }

        tweet_id = TwitterAPIClient.extract_tweet_id_from_url(tweet_url)
        if not tweet_id:
            raise ValueError(f"Could not extract tweet ID from URL: {tweet_url}")

        original_tweet = twitter_client.get_tweet_by_id(tweet_id)

        # Step 5: Check for thread context
        yield {
            "step": "checking_thread",
            "message": "Checking for thread context...",
            "progress": 30,
        }

        thread_tweets = None
        thread_content = None
        try:
            thread_tweets = twitter_client.get_thread_context(tweet_id)
            if thread_tweets and len(thread_tweets) > 1:
                thread_texts = [tweet.text for tweet in thread_tweets]
                thread_content = "\n\n".join(thread_texts)
                yield {
                    "step": "checking_thread",
                    "message": f"Found thread with {len(thread_tweets)} tweets",
                    "progress": 35,
                }
        except Exception:
            pass

        # Step 6: Check for linked article
        yield {
            "step": "checking_article",
            "message": "Checking for linked articles...",
            "progress": 40,
        }

        article_data = None
        article_content = None
        try:
            article_data = twitter_client.get_article_by_tweet_id(tweet_id)
            if article_data:
                article_content = article_data.get("full_text", "")
                yield {
                    "step": "checking_article",
                    "message": "Found linked article",
                    "progress": 45,
                }
        except Exception:
            pass

        # Step 7: Extract topic
        yield {
            "step": "extracting_topic",
            "message": "Extracting topic from content...",
            "progress": 50,
        }

        topic_source = original_tweet.text
        if thread_content:
            topic_source = thread_content
            if article_content:
                topic_source = (
                    f"{thread_content}\n\nArticle content:\n{article_content[:2000]}"
                )
        elif article_content:
            topic_source = (
                f"{original_tweet.text}\n\nArticle content:\n{article_content[:2000]}"
            )

        extracted_topic = ollama_client.extract_topic(topic_source)

        # Step 8: Research topic with Perplexity
        yield {
            "step": "researching",
            "message": "Researching topic with AI...",
            "progress": 55,
        }

        topic_info = None
        try:
            perplexity_client = PerplexityClient()
            research_context = thread_content if thread_content else original_tweet.text
            if article_content:
                research_context = f"{research_context}\n\nRelated article content:\n{article_content[:1500]}"

            if deep_research:
                yield {
                    "step": "researching",
                    "message": "Performing deep research...",
                    "progress": 60,
                }
                if use_full_content:
                    topic_info = perplexity_client.deep_research_topic(
                        topic=topic_source, original_tweet_text=None
                    )
                else:
                    topic_info = perplexity_client.deep_research_topic(
                        topic=extracted_topic, original_tweet_text=research_context
                    )
            else:
                topic_info = perplexity_client.search_topic(
                    extracted_topic, original_tweet_text=research_context
                )
            yield {
                "step": "researching",
                "message": "Research complete",
                "progress": 65,
            }
        except ValueError:
            yield {
                "step": "researching",
                "message": "Skipping research (API key not set)",
                "progress": 65,
            }
        except PerplexityError:
            yield {
                "step": "researching",
                "message": "Research unavailable, continuing...",
                "progress": 65,
            }

        # Step 9: Analyze voice profile
        yield {
            "step": "analyzing_voice",
            "message": f"Analyzing @{username}'s writing style...",
            "progress": 70,
        }

        if profile_file:
            profile_path = Path(profile_file)
            if not profile_path.exists():
                raise FileNotFoundError(f"Profile file not found: {profile_file}")
            profile_data = json.loads(profile_path.read_text())
            voice_profile = VoiceProfile(**profile_data)
        else:
            # Now use cached tweets (they should exist from earlier fetch)
            analyzer = VoiceAnalyzer(
                twitter_client, ollama_client, max_tweets=1000, prefer_cache_only=True
            )
            voice_profile = analyzer.analyze(username)

        # Build context
        final_topic = topic_info if topic_info else extracted_topic

        if thread_content:
            original_tweet_context = f"Thread by @{original_tweet.author_username} ({len(thread_tweets)} tweets):\n{thread_content}"
        else:
            original_tweet_context = f"Original tweet by @{original_tweet.author_username}:\n{original_tweet.text}"

        if article_content:
            original_tweet_context += (
                f"\n\nArticle linked in tweet:\n{article_content[:2000]}"
            )

        if context:
            original_tweet_context += f"\n\nAdditional context:\n{context}"

        # Store research for potential regeneration
        from twitter_agent.api.research_cache import store_research

        research_id = store_research(
            username=username,
            tweet_url=tweet_url,
            original_tweet=original_tweet.model_dump(mode="json"),
            topic_info=topic_info,
            extracted_topic=extracted_topic,
            original_tweet_context=original_tweet_context,
            voice_profile=voice_profile.model_dump(mode="json"),
            thread_content=thread_content,
            article_content=article_content,
        )

        # Step 10: Generate content
        yield {
            "step": "generating",
            "message": "Generating content proposals...",
            "progress": 80,
        }

        generate_all = content_type.lower() == "all"
        if not generate_all:
            try:
                requested_type = ContentType(content_type.lower())
            except ValueError:
                raise ValueError(
                    f"Invalid content type '{content_type}'. Use: tweet, thread, reply, quote, or all"
                )

        generator = ContentGenerator(
            ollama_client=ollama_client,
            voice_profile=voice_profile,
            file_processor=None,
            analytics_processor=None,
            calendar_processor=None,
        )

        qt_proposals = []
        tweet_proposals = []
        reply_proposals = []
        thread_proposals = []

        if generate_all or content_type.lower() == "quote":
            yield {
                "step": "generating",
                "message": "Generating quote tweet...",
                "progress": 82,
            }
            qt_proposals = generator.generate(
                content_type=ContentType.QUOTE,
                use_content=False,
                use_analytics=False,
                use_calendar=False,
                count=1,
                topic=final_topic,
                original_tweet_context=original_tweet_context,
                vibe=vibe,
            )

        if generate_all or content_type.lower() == "tweet":
            yield {
                "step": "generating",
                "message": "Generating standalone tweet...",
                "progress": 86,
            }
            tweet_proposals = generator.generate(
                content_type=ContentType.TWEET,
                use_content=False,
                use_analytics=False,
                use_calendar=False,
                count=1,
                topic=final_topic,
                original_tweet_context=None,
                vibe=vibe,
            )

        if generate_all or content_type.lower() == "reply":
            yield {
                "step": "generating",
                "message": "Generating reply...",
                "progress": 90,
            }
            reply_proposals = generator.generate(
                content_type=ContentType.REPLY,
                use_content=False,
                use_analytics=False,
                use_calendar=False,
                count=1,
                topic=final_topic,
                original_tweet_context=original_tweet_context,
                vibe=vibe,
            )

        if content_type.lower() == "thread":
            yield {
                "step": "generating",
                "message": "Generating thread...",
                "progress": 90,
            }
            thread_proposals = generator.generate(
                content_type=ContentType.THREAD,
                use_content=False,
                use_analytics=False,
                use_calendar=False,
                count=1,
                topic=final_topic,
                original_tweet_context=None,
                thread_count=thread_count,
                vibe=vibe,
            )

        # Convert to dicts
        original_tweet_dict = original_tweet.model_dump(mode="json")
        proposals_dict = {
            "quote": [p.model_dump(mode="json") for p in qt_proposals],
            "tweet": [p.model_dump(mode="json") for p in tweet_proposals],
            "reply": [p.model_dump(mode="json") for p in reply_proposals],
            "thread": [p.model_dump(mode="json") for p in thread_proposals],
        }

        # Final step: Complete
        yield {
            "step": "complete",
            "message": "Content generation complete!",
            "progress": 100,
            "data": {
                "original_tweet": original_tweet_dict,
                "proposals": proposals_dict,
                "research_id": research_id,
            },
        }

    finally:
        if twitter_client:
            twitter_client.close()
        if ollama_client:
            ollama_client.close()
        if perplexity_client:
            perplexity_client.close()


def propose_content(
    username: str,
    based_on: str = "all",
    content_dir: Optional[str] = None,
    calendar_file: Optional[str] = None,
    count: int = 5,
) -> list[dict]:
    """
    Propose content based on analytics, calendar, or content context.

    Returns:
        List of proposal dictionaries
    """
    config = get_config()
    if not config["twitter_api_key"]:
        raise ValueError("TWITTER_API_KEY environment variable not set")

    twitter_client = None
    ollama_client = None

    try:
        # Initialize clients
        twitter_client = TwitterAPIClient(api_key=config["twitter_api_key"])
        ollama_client = OllamaClient(
            base_url=config["ollama_base_url"], model=config["ollama_model"]
        )

        # Check Ollama availability
        if not ollama_client.check_available():
            raise ValueError(
                f"Ollama is not available at {config['ollama_base_url']}. "
                f"Make sure Ollama is running and model '{config['ollama_model']}' is installed."
            )

        # Analyze voice
        analyzer = VoiceAnalyzer(twitter_client, ollama_client)
        voice_profile = analyzer.analyze(username)

        # Initialize processors
        content_dir_path = content_dir or config["content_dir"]
        file_processor = FileProcessor(content_dir=content_dir_path)

        use_analytics = based_on in ["analytics", "all"]
        use_calendar = based_on in ["calendar", "all"]
        use_content = based_on in ["content", "all"]

        analytics_processor = None
        if use_analytics:
            tweets = twitter_client.get_user_tweets(username, max_results=1000)
            if tweets:
                analytics_processor = AnalyticsProcessor(tweets)

        calendar_processor = None
        if use_calendar and calendar_file:
            calendar_processor = CalendarProcessor(calendar_file=calendar_file)
            calendar_processor.load_calendar()

        # Generate proposals
        generator = ContentGenerator(
            ollama_client=ollama_client,
            voice_profile=voice_profile,
            file_processor=file_processor if use_content else None,
            analytics_processor=analytics_processor,
            calendar_processor=calendar_processor,
        )

        proposals = generator.generate(
            content_type=ContentType.TWEET,
            use_content=use_content,
            use_analytics=use_analytics,
            use_calendar=use_calendar,
            count=count,
        )

        # Convert proposals to dicts
        return [proposal.model_dump(mode="json") for proposal in proposals]

    finally:
        if twitter_client:
            twitter_client.close()
        if ollama_client:
            ollama_client.close()


def check_configuration() -> dict:
    """
    Check configuration and dependencies.

    Returns:
        Dictionary with status, config, and errors
    """
    config = get_config()
    status = {}
    errors = []

    # Check Twitter API key
    if config["twitter_api_key"]:
        status["twitter_api_key"] = True
    else:
        status["twitter_api_key"] = False
        errors.append("TWITTER_API_KEY is not set")

    # Check Ollama
    ollama_client = OllamaClient(
        base_url=config["ollama_base_url"], model=config["ollama_model"]
    )
    if ollama_client.check_available():
        status["ollama"] = True
        status["ollama_url"] = config["ollama_base_url"]
        status["ollama_model"] = config["ollama_model"]
    else:
        status["ollama"] = False
        errors.append(
            f"Ollama not available at {config['ollama_base_url']}. Make sure Ollama is running: ollama serve"
        )

    ollama_client.close()

    # Check content directory
    content_dir = Path(config["content_dir"])
    if content_dir.exists():
        file_processor = FileProcessor(content_dir=config["content_dir"])
        file_count = file_processor.get_files_count()
        status["content_dir"] = True
        status["content_dir_path"] = config["content_dir"]
        status["content_files"] = file_count
    else:
        status["content_dir"] = False
        status["content_dir_path"] = config["content_dir"]

    # Check cache
    cache = TwitterCache()
    if cache.cache_dir.exists():
        cache_files = list(cache.cache_dir.glob("*.json"))
        status["cache"] = True
        status["cache_dir"] = str(cache.cache_dir)
        status["cache_files"] = len(cache_files)
    else:
        status["cache"] = False
        status["cache_dir"] = str(cache.cache_dir)

    return {"status": status, "config": config, "errors": errors if errors else None}


def get_cache_info(username: Optional[str] = None) -> dict:
    """
    Get cache information.

    Returns:
        Dictionary with cache information
    """
    cache = TwitterCache()

    if username:
        info = cache.get_cache_info(username)
        return {"username": username, "info": info}
    else:
        # Show all cached usernames
        if not cache.cache_dir.exists():
            return {"usernames": []}

        cache_files = list(cache.cache_dir.glob("*.json"))
        if not cache_files:
            return {"usernames": []}

        # Extract unique usernames
        usernames = set()
        for cache_file in cache_files:
            name = cache_file.stem
            if name.startswith("user_info_"):
                usernames.add(name.replace("user_info_", ""))
            elif name.startswith("tweets_"):
                usernames.add(name.replace("tweets_", ""))

        # Get info for each username
        result = []
        for uname in sorted(usernames):
            info = cache.get_cache_info(uname)
            result.append({"username": uname, "info": info})

        return {"usernames": result}


def clear_cache(username: Optional[str] = None) -> dict:
    """
    Clear cache for a username or all cache.

    Returns:
        Dictionary with success status and message
    """
    cache = TwitterCache()

    if username:
        cache.invalidate_all(username)
        return {"success": True, "message": f"Cleared cache for @{username}"}
    else:
        cache.clear_all()
        return {"success": True, "message": "Cleared all cache files"}


def regenerate_from_research(
    research_id: str,
    content_type: str = "all",
    thread_count: int = 5,
    vibe: Optional[str] = None,
    context: Optional[str] = None,
    suggestions: Optional[str] = None,
) -> dict:
    """
    Regenerate content using stored research results.

    Returns:
        Dictionary with proposals
    """
    config = get_config()
    if not config["twitter_api_key"]:
        raise ValueError("TWITTER_API_KEY environment variable not set")

    # Get stored research
    research = get_research(research_id)
    if not research:
        raise ValueError(f"Research ID not found or expired: {research_id}")

    ollama_client = None

    try:
        # Initialize Ollama client
        ollama_client = OllamaClient(
            base_url=config["ollama_base_url"], model=config["ollama_model"]
        )

        # Check Ollama availability
        if not ollama_client.check_available():
            raise ValueError(
                f"Ollama is not available at {config['ollama_base_url']}. "
                f"Make sure Ollama is running and model '{config['ollama_model']}' is installed."
            )

        # Reconstruct voice profile from stored data
        voice_profile = VoiceProfile(**research["voice_profile"])

        # Use researched topic info if available, otherwise use extracted topic
        final_topic = (
            research["topic_info"]
            if research["topic_info"]
            else research["extracted_topic"]
        )

        # Incorporate suggestions/changes into the topic if provided
        if suggestions:
            final_topic = f"{final_topic}\n\nModification instructions: {suggestions}"

        # Build context (add user-provided context if given)
        original_tweet_context = research["original_tweet_context"]
        if context:
            original_tweet_context = (
                f"{original_tweet_context}\n\nAdditional context:\n{context}"
            )

        # Parse content type
        generate_all = content_type.lower() == "all"
        if not generate_all:
            try:
                requested_type = ContentType(content_type.lower())
            except ValueError:
                raise ValueError(
                    f"Invalid content type '{content_type}'. Use: tweet, thread, reply, quote, or all"
                )

        # Generate content
        generator = ContentGenerator(
            ollama_client=ollama_client,
            voice_profile=voice_profile,
            file_processor=None,
            analytics_processor=None,
            calendar_processor=None,
        )

        qt_proposals = []
        tweet_proposals = []
        reply_proposals = []
        thread_proposals = []

        if generate_all or content_type.lower() == "quote":
            qt_proposals = generator.generate(
                content_type=ContentType.QUOTE,
                use_content=False,
                use_analytics=False,
                use_calendar=False,
                count=1,
                topic=final_topic,
                original_tweet_context=original_tweet_context,
                vibe=vibe,
            )

        if generate_all or content_type.lower() == "tweet":
            tweet_proposals = generator.generate(
                content_type=ContentType.TWEET,
                use_content=False,
                use_analytics=False,
                use_calendar=False,
                count=1,
                topic=final_topic,
                original_tweet_context=None,
                vibe=vibe,
            )

        if generate_all or content_type.lower() == "reply":
            reply_proposals = generator.generate(
                content_type=ContentType.REPLY,
                use_content=False,
                use_analytics=False,
                use_calendar=False,
                count=1,
                topic=final_topic,
                original_tweet_context=original_tweet_context,
                vibe=vibe,
            )

        if content_type.lower() == "thread":
            thread_proposals = generator.generate(
                content_type=ContentType.THREAD,
                use_content=False,
                use_analytics=False,
                use_calendar=False,
                count=1,
                topic=final_topic,
                original_tweet_context=None,
                thread_count=thread_count,
                vibe=vibe,
            )

        # Convert to dicts
        proposals_dict = {
            "quote": [p.model_dump(mode="json") for p in qt_proposals],
            "tweet": [p.model_dump(mode="json") for p in tweet_proposals],
            "reply": [p.model_dump(mode="json") for p in reply_proposals],
            "thread": [p.model_dump(mode="json") for p in thread_proposals],
        }

        return proposals_dict

    finally:
        if ollama_client:
            ollama_client.close()
