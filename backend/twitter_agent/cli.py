"""CLI interface for Twitter Agent."""

import json
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table

from twitter_agent.analysis.content_generator import ContentGenerator
from twitter_agent.analysis.voice_analyzer import VoiceAnalyzer
from twitter_agent.clients.twitter import TwitterAPIClient
from twitter_agent.llm.ollama_client import OllamaClient
from twitter_agent.llm.perplexity_client import PerplexityClient, PerplexityError
from twitter_agent.models.schemas import ContentType
from twitter_agent.utils.analytics import AnalyticsProcessor
from twitter_agent.utils.calendar import CalendarProcessor
from twitter_agent.utils.file_processor import FileProcessor
from twitter_agent.utils.cache import TwitterCache

app = typer.Typer(
    help="Twitter Voice Agent - Analyze voices and generate content proposals"
)
console = Console()


# Configuration
def get_config() -> dict:
    """Get configuration from environment variables."""
    return {
        "twitter_api_key": os.getenv("TWITTER_API_KEY"),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "llama3.2"),
        "content_dir": os.getenv("CONTENT_DIR", "content"),
    }


@app.command()
def analyze(
    username: str = typer.Argument(..., help="Twitter username (without @)"),
    max_tweets: int = typer.Option(
        100, "--max-tweets", "-n", help="Maximum tweets to analyze"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file for profile"
    ),
):
    """
    Analyze a Twitter user's voice and persona.
    """
    config = get_config()
    if not config["twitter_api_key"]:
        console.print("[red]Error: TWITTER_API_KEY environment variable not set[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Analyzing voice for @{username}...[/cyan]")

    try:
        # Initialize clients
        twitter_client = TwitterAPIClient(api_key=config["twitter_api_key"])
        ollama_client = OllamaClient(
            base_url=config["ollama_base_url"], model=config["ollama_model"]
        )

        # Check Ollama availability
        if not ollama_client.check_available():
            console.print(
                "[yellow]Warning: Ollama may not be available. "
                "Make sure Ollama is running and the model is installed.[/yellow]"
            )

        # Analyze voice
        analyzer = VoiceAnalyzer(twitter_client, ollama_client, max_tweets=max_tweets)
        voice_profile = analyzer.analyze(username)

        # Display results
        console.print("\n[bold green]Voice Analysis Complete![/bold green]\n")

        table = Table(title=f"Voice Profile: @{username}")
        table.add_column("Attribute", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Writing Style", voice_profile.writing_style[:100])
        table.add_row("Tone", voice_profile.tone[:100])
        table.add_row(
            "Common Topics",
            (
                ", ".join(voice_profile.common_topics[:5])
                if voice_profile.common_topics
                else "None"
            ),
        )
        table.add_row(
            "Avg Tweet Length",
            (
                f"{voice_profile.average_tweet_length} chars"
                if voice_profile.average_tweet_length
                else "N/A"
            ),
        )
        table.add_row(
            "Top Hashtags",
            (
                ", ".join(list(voice_profile.hashtag_usage.keys())[:5])
                if voice_profile.hashtag_usage
                else "None"
            ),
        )

        console.print(table)

        # Save to file if requested
        if output:
            output_path = Path(output)
            profile_dict = voice_profile.model_dump(mode="json")
            output_path.write_text(json.dumps(profile_dict, indent=2, default=str))
            console.print(f"\n[green]Profile saved to {output_path}[/green]")

        twitter_client.close()
        ollama_client.close()

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def generate(
    username: str = typer.Argument(..., help="Twitter username (without @)"),
    content_type: str = typer.Option(
        "tweet", "--type", "-t", help="Content type: tweet, thread, reply, quote"
    ),
    content_dir: Optional[str] = typer.Option(
        None, "--content-dir", "-d", help="Content directory"
    ),
    calendar_file: Optional[str] = typer.Option(
        None, "--calendar", "-c", help="Calendar file (JSON/YAML)"
    ),
    count: int = typer.Option(
        1, "--count", "-n", help="Number of proposals to generate"
    ),
    use_analytics: bool = typer.Option(
        True, "--analytics/--no-analytics", help="Use engagement analytics"
    ),
    use_calendar: bool = typer.Option(
        True, "--calendar-hints/--no-calendar-hints", help="Use calendar hints"
    ),
    profile_file: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Load voice profile from file"
    ),
    topic: Optional[str] = typer.Option(
        None, "--topic", "-T", help="Topic or text to generate tweet about"
    ),
    thread_count: int = typer.Option(
        5,
        "--thread-count",
        help="Number of tweets in a thread (only used with --type thread)",
    ),
):
    """
    Generate content proposals based on analyzed voice.
    """
    config = get_config()
    if not config["twitter_api_key"]:
        console.print("[red]Error: TWITTER_API_KEY environment variable not set[/red]")
        raise typer.Exit(1)

    # Parse content type
    try:
        content_type_enum = ContentType(content_type.lower())
    except ValueError:
        console.print(
            f"[red]Error: Invalid content type '{content_type}'. Use: tweet, thread, reply, quote[/red]"
        )
        raise typer.Exit(1)

    console.print(
        f"[cyan]Generating {content_type} proposals for @{username}...[/cyan]"
    )

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
            console.print(
                "[red]Error: Ollama is not available. "
                "Make sure Ollama is running and the model is installed.[/red]"
            )
            console.print(
                f"[yellow]Check: ollama serve (at {config['ollama_base_url']})[/yellow]"
            )
            console.print(f"[yellow]Model needed: {config['ollama_model']}[/yellow]")
            raise typer.Exit(1)

        # Load or analyze voice profile
        if profile_file:
            console.print(f"[cyan]Loading voice profile from {profile_file}...[/cyan]")
            profile_path = Path(profile_file)
            if not profile_path.exists():
                console.print(
                    f"[red]Error: Profile file not found: {profile_file}[/red]"
                )
                raise typer.Exit(1)
            profile_data = json.loads(profile_path.read_text())
            from twitter_agent.models.schemas import VoiceProfile

            voice_profile = VoiceProfile(**profile_data)
        else:
            console.print("[cyan]Analyzing voice first...[/cyan]")
            # Use cached tweets only for generate command - don't fetch from API
            analyzer = VoiceAnalyzer(
                twitter_client, ollama_client, max_tweets=1000, prefer_cache_only=True
            )
            voice_profile = analyzer.analyze(username)

        # Initialize processors
        content_dir_path = content_dir or config["content_dir"]
        file_processor = FileProcessor(content_dir=content_dir_path)

        analytics_processor = None
        if use_analytics:
            console.print("[cyan]Fetching tweets for analytics...[/cyan]")
            # Use cached tweets only for generate command
            tweets = twitter_client.get_user_tweets(
                username, max_results=1000, prefer_cache_only=True
            )
            if tweets:
                analytics_processor = AnalyticsProcessor(tweets)
                console.print(
                    f"[green]✓ Loaded {len(tweets)} cached tweets for analytics[/green]"
                )
            else:
                console.print(
                    "[yellow]Warning: No cached tweets found for analytics[/yellow]"
                )

        calendar_processor = None
        if use_calendar and calendar_file:
            calendar_processor = CalendarProcessor(calendar_file=calendar_file)
            calendar_processor.load_calendar()
            console.print("[green]✓ Calendar loaded[/green]")

        # Fetch topic information from Perplexity if topic is provided
        topic_info = None
        perplexity_client = None
        if topic:
            try:
                console.print(f"[cyan]Researching topic: {topic}...[/cyan]")
                perplexity_client = PerplexityClient()
                topic_info = perplexity_client.search_topic(topic)
                console.print(f"[green]✓ Topic research completed[/green]")
            except ValueError:
                console.print(
                    "[yellow]Warning: PERPLEXITY_API_KEY not set, skipping topic research[/yellow]"
                )
            except PerplexityError as e:
                console.print(
                    f"[yellow]Warning: Failed to fetch topic information: {str(e)}[/yellow]"
                )
                console.print("[yellow]Continuing without topic research...[/yellow]")

        # Generate content
        console.print("[cyan]Generating content proposals...[/cyan]")
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
            topic=(
                topic_info if topic_info else topic
            ),  # Use researched info if available
            thread_count=thread_count,
        )

        # Display proposals
        console.print(
            f"\n[bold green]Generated {len(proposals)} {content_type} proposal(s):[/bold green]\n"
        )

        for i, proposal in enumerate(proposals, 1):
            panel_content = []
            if isinstance(proposal.content, list):
                panel_content.append("[bold]Thread:[/bold]\n")
                for j, tweet in enumerate(proposal.content, 1):
                    panel_content.append(f"{j}. {tweet}\n")
            else:
                panel_content.append(proposal.content)

            if proposal.suggested_date:
                panel_content.append(
                    f"\n[dim]Suggested date: {proposal.suggested_date.strftime('%Y-%m-%d %H:%M')}[/dim]"
                )
            if proposal.based_on:
                panel_content.append(
                    f"\n[dim]Based on: {', '.join(proposal.based_on)}[/dim]"
                )

            console.print(
                Panel(
                    "".join(panel_content), title=f"Proposal {i}", border_style="green"
                )
            )

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        import traceback

        console.print(f"[red]Error: {str(e)}[/red]")
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)
    finally:
        if twitter_client:
            twitter_client.close()
        if ollama_client:
            ollama_client.close()


@app.command()
def inspire(
    username: str = typer.Argument(..., help="Twitter username (without @)"),
    tweet_url: str = typer.Argument(
        ..., help="Tweet URL to read and generate inspired content from"
    ),
    content_type: str = typer.Option(
        "all",
        "--type",
        "-t",
        help="Content type to generate: tweet, thread, reply, quote, or all (default: all)",
    ),
    profile_file: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Load voice profile from file"
    ),
    thread_count: int = typer.Option(
        5,
        "--thread-count",
        help="Number of tweets in a thread (only used with --type thread)",
    ),
    vibe: Optional[str] = typer.Option(
        None,
        "--vibe",
        "-v",
        help="Vibe/mood for the generated content (e.g., 'positive and excited', 'skeptical and questioning', 'angry and frustrated', 'curious and playful'). Describes the tone and emotional state.",
    ),
    deep_research: bool = typer.Option(
        False,
        "--deep-research",
        help="Use deep research mode: combines multiple sonar models (sonar-pro + sonar-online) and search API for comprehensive, multi-perspective research",
    ),
    use_full_content: bool = typer.Option(
        False,
        "--use-full-content",
        help="Use full content for research instead of topic summary. By default, uses extracted topic summary.",
    ),
):
    """
    Read a tweet from a URL, extract its topic, research it with Perplexity, and generate content in the user's voice.

    By default generates three options (all):
    - A quote tweet (QT) commenting on the original tweet
    - A standalone tweet about the topic
    - A reply to the original tweet

    Use --type to generate a specific type instead.
    """
    config = get_config()
    if not config["twitter_api_key"]:
        console.print("[red]Error: TWITTER_API_KEY environment variable not set[/red]")
        raise typer.Exit(1)

    console.print(
        f"[cyan]Reading tweet from URL and generating three content options for @{username}...[/cyan]"
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
        try:
            ollama_client.client.get("/api/tags")
        except Exception:
            console.print(
                "[red]Error: Cannot connect to Ollama. Make sure Ollama is running and the model is installed.[/red]"
            )
            console.print(
                f"[yellow]Check: ollama serve (at {config['ollama_base_url']})[/yellow]"
            )
            console.print(f"[yellow]Model needed: {config['ollama_model']}[/yellow]")
            raise typer.Exit(1)

        # Extract tweet ID from URL
        console.print(f"[cyan]Extracting tweet ID from URL...[/cyan]")
        tweet_id = TwitterAPIClient.extract_tweet_id_from_url(tweet_url)
        if not tweet_id:
            console.print(
                f"[red]Error: Could not extract tweet ID from URL: {tweet_url}[/red]"
            )
            console.print(
                "[yellow]Please provide a valid Twitter/X URL (e.g., https://twitter.com/username/status/1234567890)[/yellow]"
            )
            raise typer.Exit(1)

        # Fetch the tweet
        console.print(f"[cyan]Fetching tweet {tweet_id}...[/cyan]")
        original_tweet = twitter_client.get_tweet_by_id(tweet_id)
        console.print(
            f"[green]✓ Fetched tweet from @{original_tweet.author_username}[/green]\n"
        )
        console.print(f"[dim]{original_tweet.text}[/dim]\n")

        # Check if tweet is part of a thread
        thread_tweets = None
        thread_content = None
        try:
            console.print(f"[cyan]Checking if tweet is part of a thread...[/cyan]")
            thread_tweets = twitter_client.get_thread_context(tweet_id)
            if thread_tweets and len(thread_tweets) > 1:
                # Combine all thread tweets' text
                thread_texts = [tweet.text for tweet in thread_tweets]
                thread_content = "\n\n".join(thread_texts)
                console.print(
                    f"[green]✓ Found thread with {len(thread_tweets)} tweets ({len(thread_content)} characters)[/green]\n"
                )
            else:
                console.print(f"[dim]Tweet is not part of a thread[/dim]\n")
        except Exception as e:
            from loguru import logger

            logger.warning(f"Error fetching thread context: {e}")
            console.print(
                f"[yellow]Warning: Could not fetch thread context: {e}[/yellow]\n"
            )

        # Check if tweet links to an article using TwitterAPI.io
        article_data = None
        article_content = None
        try:
            console.print(f"[cyan]Checking for article linked in tweet...[/cyan]")
            article_data = twitter_client.get_article_by_tweet_id(tweet_id)
            if article_data:
                article_content = article_data.get("full_text", "")
                article_title = article_data.get("title", "Untitled")
                if article_content:
                    console.print(
                        f"[green]✓ Found article: '{article_title}' ({len(article_content)} characters)[/green]\n"
                    )
                else:
                    console.print(
                        f"[dim]Article found but no content extracted[/dim]\n"
                    )
            else:
                console.print(f"[dim]No article found in tweet[/dim]\n")
        except Exception as e:
            from loguru import logger

            logger.warning(f"Error fetching article: {e}")
            console.print(
                f"[yellow]Warning: Could not fetch article data: {e}[/yellow]\n"
            )

        # Extract topic from the tweet (and thread/article if available)
        topic_source = original_tweet.text
        if thread_content:
            # Use thread content instead of just the single tweet
            topic_source = thread_content
            if article_content:
                # Add article content to thread context
                topic_source = (
                    f"{thread_content}\n\nArticle content:\n{article_content[:2000]}"
                )
        elif article_content:
            # Combine tweet text and article content for topic extraction
            topic_source = f"{original_tweet.text}\n\nArticle content:\n{article_content[:2000]}"  # Limit article content to avoid token limits

        # Extract topic summary (always needed for standard research and optional for deep research)
        console.print(f"[cyan]Extracting topic summary from content...[/cyan]")
        extracted_topic = ollama_client.extract_topic(topic_source)
        console.print(
            f"[green]✓ Extracted topic summary: {extracted_topic[:100]}...[/green]\n"
        )

        # Research topic with Perplexity (with original tweet/thread context and article if available)
        topic_info = None
        try:
            perplexity_client = PerplexityClient()
            # Use thread content if available, otherwise use single tweet
            research_context = thread_content if thread_content else original_tweet.text
            if article_content:
                research_context = f"{research_context}\n\nRelated article content:\n{article_content[:1500]}"

            if deep_research:
                if use_full_content:
                    # Use the FULL original content as the topic
                    # sonar-deep-research can handle large context (128K) and will search more comprehensively
                    console.print(
                        f"[cyan]Performing deep research on full content (multiple models + search)...[/cyan]"
                    )
                    topic_info = perplexity_client.deep_research_topic(
                        topic=topic_source,  # Use full content instead of summary
                        original_tweet_text=None,  # Already included in topic
                    )
                else:
                    # Use extracted summary for deep research (default, more focused, token-efficient)
                    console.print(
                        f"[cyan]Performing deep research on topic summary (multiple models + search)...[/cyan]"
                    )
                    topic_info = perplexity_client.deep_research_topic(
                        topic=extracted_topic,  # Use summary
                        original_tweet_text=research_context,  # Additional context
                    )
            else:
                # For standard research, always use the extracted summary (more token-efficient)
                console.print(
                    f"[cyan]Researching topic summary with Perplexity...[/cyan]"
                )
                topic_info = perplexity_client.search_topic(
                    extracted_topic, original_tweet_text=research_context
                )
            console.print(f"[green]✓ Topic research completed[/green]\n")
        except ValueError:
            console.print(
                "[yellow]Warning: PERPLEXITY_API_KEY not set, skipping topic research[/yellow]\n"
            )
        except PerplexityError as e:
            console.print(
                f"[yellow]Warning: Failed to fetch topic information: {str(e)}[/yellow]\n"
            )
            console.print("[yellow]Continuing without topic research...[/yellow]\n")

        # Load or analyze voice profile
        if profile_file:
            profile_path = Path(profile_file)
            if not profile_path.exists():
                console.print(
                    f"[red]Error: Profile file not found: {profile_file}[/red]"
                )
                raise typer.Exit(1)
            profile_data = json.loads(profile_path.read_text())
            from twitter_agent.models.schemas import VoiceProfile

            voice_profile = VoiceProfile(**profile_data)
        else:
            console.print("[cyan]Analyzing voice first...[/cyan]")
            # Use cached tweets only - don't fetch from API
            analyzer = VoiceAnalyzer(
                twitter_client, ollama_client, max_tweets=1000, prefer_cache_only=True
            )
            voice_profile = analyzer.analyze(username)
            console.print("[green]✓ Voice analysis completed[/green]\n")

        # Use researched topic info if available, otherwise use extracted topic
        final_topic = topic_info if topic_info else extracted_topic

        # Build context including thread and article if available
        if thread_content:
            # Use thread content
            original_tweet_context = f"Thread by @{original_tweet.author_username} ({len(thread_tweets)} tweets):\n{thread_content}"
        else:
            original_tweet_context = f"Original tweet by @{original_tweet.author_username}:\n{original_tweet.text}"

        if article_content:
            original_tweet_context += (
                f"\n\nArticle linked in tweet:\n{article_content[:2000]}"
            )

        # Parse content type
        generate_all = content_type.lower() == "all"
        if not generate_all:
            try:
                requested_type = ContentType(content_type.lower())
            except ValueError:
                console.print(
                    f"[red]Error: Invalid content type '{content_type}'. Use: tweet, thread, reply, quote, or all[/red]"
                )
                raise typer.Exit(1)

        # Generate content
        if generate_all:
            console.print("[cyan]Generating three content options...[/cyan]")
        else:
            console.print(f"[cyan]Generating {content_type} content...[/cyan]")

        generator = ContentGenerator(
            ollama_client=ollama_client,
            voice_profile=voice_profile,
            file_processor=None,  # Don't use file processor for inspire command
            analytics_processor=None,  # Don't use analytics for inspire command
            calendar_processor=None,  # Don't use calendar for inspire command
        )

        qt_proposals = []
        tweet_proposals = []
        reply_proposals = []
        thread_proposals = []

        if generate_all or content_type.lower() == "quote":
            # Generate Quote Tweet
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
            # Generate Standalone Tweet
            tweet_proposals = generator.generate(
                content_type=ContentType.TWEET,
                use_content=False,
                use_analytics=False,
                use_calendar=False,
                count=1,
                topic=final_topic,
                original_tweet_context=None,  # No original tweet context for standalone
                vibe=vibe,
            )

        if generate_all or content_type.lower() == "reply":
            # Generate Reply
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
            # Generate Thread
            thread_proposals = generator.generate(
                content_type=ContentType.THREAD,
                use_content=False,
                use_analytics=False,
                use_calendar=False,
                count=1,
                topic=final_topic,
                original_tweet_context=None,  # Threads are standalone, not replies
                thread_count=thread_count,
                vibe=vibe,
            )

        # Display original tweet
        console.print(f"\n[bold cyan]Original Tweet:[/bold cyan]")
        original_tweet_display = (
            f"@{original_tweet.author_username}\n{original_tweet.text}"
        )
        if original_tweet.like_count or original_tweet.retweet_count:
            stats = []
            if original_tweet.like_count:
                stats.append(f"❤️ {original_tweet.like_count}")
            if original_tweet.retweet_count:
                stats.append(f"🔁 {original_tweet.retweet_count}")
            original_tweet_display += f"\n[dim]{' · '.join(stats)}[/dim]"
        console.print(Panel(original_tweet_display, border_style="cyan"))

        # Display proposals
        if generate_all:
            console.print(
                f"\n[bold green]Generated 3 content options inspired by this tweet:[/bold green]\n"
            )
        else:
            console.print(
                f"\n[bold green]Generated {content_type} content inspired by this tweet:[/bold green]\n"
            )

        # Display Quote Tweet
        if qt_proposals:
            qt_content = qt_proposals[0].content
            if isinstance(qt_content, list):
                qt_content = "\n".join(qt_content)
            title = (
                "[bold]Quote Tweet (QT)[/bold]"
                if not generate_all
                else "[bold]1. Quote Tweet (QT)[/bold]"
            )
            console.print(
                Panel(
                    qt_content,
                    title=title,
                    border_style="blue",
                )
            )
            console.print()

        # Display Standalone Tweet
        if tweet_proposals:
            tweet_content = tweet_proposals[0].content
            if isinstance(tweet_content, list):
                tweet_content = "\n".join(tweet_content)
            title = (
                "[bold]Tweet[/bold]"
                if not generate_all
                else "[bold]2. Standalone Tweet[/bold]"
            )
            console.print(
                Panel(
                    tweet_content,
                    title=title,
                    border_style="green",
                )
            )
            console.print()

        # Display Reply
        if reply_proposals:
            reply_content = reply_proposals[0].content
            if isinstance(reply_content, list):
                reply_content = "\n".join(reply_content)
            title = (
                "[bold]Reply[/bold]" if not generate_all else "[bold]3. Reply[/bold]"
            )
            console.print(
                Panel(
                    reply_content,
                    title=title,
                    border_style="yellow",
                )
            )
            console.print()

        # Display Thread
        if thread_proposals:
            thread_content_display = thread_proposals[0].content
            if isinstance(thread_content_display, list):
                panel_content = []
                for j, tweet in enumerate(thread_content_display, 1):
                    panel_content.append(f"{j}. {tweet}\n")
                thread_content_display = "".join(panel_content)
            console.print(
                Panel(
                    thread_content_display,
                    title="[bold]Thread[/bold]",
                    border_style="cyan",
                )
            )

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        import traceback

        console.print(f"[red]Error: {str(e)}[/red]")
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)
    finally:
        if twitter_client:
            twitter_client.close()
        if ollama_client:
            ollama_client.close()
        if perplexity_client:
            perplexity_client.close()


@app.command()
def propose(
    username: str = typer.Argument(..., help="Twitter username (without @)"),
    based_on: str = typer.Option(
        "all",
        "--based-on",
        "-b",
        help="Base proposals on: analytics, calendar, content, or all",
    ),
    content_dir: Optional[str] = typer.Option(
        None, "--content-dir", "-d", help="Content directory"
    ),
    calendar_file: Optional[str] = typer.Option(
        None, "--calendar", "-c", help="Calendar file (JSON/YAML)"
    ),
    count: int = typer.Option(
        5, "--count", "-n", help="Number of proposals to generate"
    ),
):
    """
    Propose content based on analytics, calendar, or content context.
    """
    config = get_config()
    if not config["twitter_api_key"]:
        console.print("[red]Error: TWITTER_API_KEY environment variable not set[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Generating content proposals for @{username}...[/cyan]")

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
            console.print(
                "[red]Error: Ollama is not available. "
                "Make sure Ollama is running and the model is installed.[/red]"
            )
            console.print(
                f"[yellow]Check: ollama serve (at {config['ollama_base_url']})[/yellow]"
            )
            console.print(f"[yellow]Model needed: {config['ollama_model']}[/yellow]")
            raise typer.Exit(1)

        # Analyze voice
        console.print("[cyan]Analyzing voice...[/cyan]")
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
            console.print("[cyan]Fetching tweets for analytics...[/cyan]")
            # Use a large number to get all available cached tweets, or fetch up to 1000
            tweets = twitter_client.get_user_tweets(username, max_results=1000)
            if tweets:
                analytics_processor = AnalyticsProcessor(tweets)
                console.print(
                    f"[green]✓ Analytics loaded ({len(tweets)} tweets)[/green]"
                )
            else:
                console.print("[yellow]Warning: No tweets found for analytics[/yellow]")

        calendar_processor = None
        if use_calendar:
            if calendar_file:
                calendar_processor = CalendarProcessor(calendar_file=calendar_file)
                calendar_processor.load_calendar()
                console.print("[green]✓ Calendar loaded[/green]")
            else:
                console.print(
                    "[yellow]Warning: Calendar file not provided, skipping calendar hints[/yellow]"
                )
                use_calendar = False

        if use_content:
            file_count = file_processor.get_files_count()
            if file_count > 0:
                console.print(f"[green]✓ Found {file_count} content file(s)[/green]")
            else:
                console.print("[yellow]Warning: No content files found[/yellow]")

        # Generate proposals
        console.print("[cyan]Generating content proposals...[/cyan]")
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

        # Display proposals
        console.print(
            f"\n[bold green]Generated {len(proposals)} proposal(s):[/bold green]\n"
        )

        for i, proposal in enumerate(proposals, 1):
            panel_content = [
                (
                    proposal.content
                    if isinstance(proposal.content, str)
                    else "\n".join(proposal.content)
                )
            ]
            if proposal.suggested_date:
                panel_content.append(
                    f"\n[dim]📅 Suggested: {proposal.suggested_date.strftime('%Y-%m-%d %H:%M')}[/dim]"
                )
            if proposal.based_on:
                panel_content.append(
                    f"\n[dim]📊 Based on: {', '.join(proposal.based_on)}[/dim]"
                )

            console.print(
                Panel(
                    "".join(panel_content), title=f"Proposal {i}", border_style="cyan"
                )
            )

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        import traceback

        console.print(f"[red]Error: {str(e)}[/red]")
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)
    finally:
        if twitter_client:
            twitter_client.close()
        if ollama_client:
            ollama_client.close()


@app.command()
def check():
    """
    Check configuration and dependencies.
    """
    console.print("[cyan]Checking configuration...[/cyan]\n")

    config = get_config()

    # Check Twitter API key
    if config["twitter_api_key"]:
        console.print("[green]✓[/green] TWITTER_API_KEY is set")
    else:
        console.print("[red]✗[/red] TWITTER_API_KEY is not set")

    # Check Ollama
    ollama_client = OllamaClient(
        base_url=config["ollama_base_url"], model=config["ollama_model"]
    )
    if ollama_client.check_available():
        console.print(
            f"[green]✓[/green] Ollama is available at {config['ollama_base_url']}"
        )
        console.print(f"[green]✓[/green] Model '{config['ollama_model']}' is available")
    else:
        console.print(
            f"[red]✗[/red] Ollama not available at {config['ollama_base_url']}"
        )
        console.print("[yellow]Make sure Ollama is running: ollama serve[/yellow]")

    # Check content directory
    content_dir = Path(config["content_dir"])
    if content_dir.exists():
        file_processor = FileProcessor(content_dir=config["content_dir"])
        file_count = file_processor.get_files_count()
        console.print(
            f"[green]✓[/green] Content directory exists: {config['content_dir']} ({file_count} files)"
        )
    else:
        console.print(
            f"[yellow]⚠[/yellow] Content directory not found: {config['content_dir']}"
        )

    # Check cache
    cache = TwitterCache()
    if cache.cache_dir.exists():
        cache_files = list(cache.cache_dir.glob("*.json"))
        console.print(
            f"[green]✓[/green] Cache directory exists: {cache.cache_dir} ({len(cache_files)} files)"
        )
    else:
        console.print(
            f"[yellow]⚠[/yellow] Cache directory not found: {cache.cache_dir}"
        )

    ollama_client.close()


@app.command()
def cache_info(
    username: Optional[str] = typer.Option(
        None, "--username", "-u", help="Username to check cache for"
    ),
):
    """
    Show cache information.
    """
    cache = TwitterCache()

    if username:
        info = cache.get_cache_info(username)
        console.print(f"\n[bold]Cache info for @{username}:[/bold]\n")

        table = Table()
        table.add_column("Item", style="cyan")
        table.add_column("Status", style="green")

        if info["user_info_cached"]:
            table.add_row(
                "User Info", f"Cached ({info['user_info_age_hours']} hours old)"
            )
        else:
            table.add_row("User Info", "Not cached")

        if info["tweets_cached"]:
            table.add_row(
                "Tweets",
                f"Cached ({info['tweets_count']} tweets, {info['tweets_age_hours']} hours old)",
            )
        else:
            table.add_row("Tweets", "Not cached")

        console.print(table)
    else:
        # Show all cached usernames
        if not cache.cache_dir.exists():
            console.print("[yellow]No cache directory found[/yellow]")
            return

        cache_files = list(cache.cache_dir.glob("*.json"))
        if not cache_files:
            console.print("[yellow]No cache files found[/yellow]")
            return

        # Extract unique usernames
        usernames = set()
        for cache_file in cache_files:
            name = cache_file.stem
            if name.startswith("user_info_"):
                usernames.add(name.replace("user_info_", ""))
            elif name.startswith("tweets_"):
                usernames.add(name.replace("tweets_", ""))

        console.print(f"\n[bold]Cached usernames ({len(usernames)}):[/bold]\n")

        table = Table()
        table.add_column("Username", style="cyan")
        table.add_column("User Info", style="green")
        table.add_column("Tweets", style="green")
        table.add_column("Age (hours)", style="yellow")

        for uname in sorted(usernames):
            info = cache.get_cache_info(uname)
            user_info_status = "✓" if info["user_info_cached"] else "✗"
            tweets_status = (
                f"✓ ({info['tweets_count']})" if info["tweets_cached"] else "✗"
            )
            age = info["user_info_age_hours"] or info["tweets_age_hours"] or 0
            table.add_row(uname, user_info_status, tweets_status, f"{age:.1f}")

        console.print(table)


@app.command()
def cache_clear(
    username: Optional[str] = typer.Option(
        None,
        "--username",
        "-u",
        help="Username to clear cache for (all if not specified)",
    ),
):
    """
    Clear cache for a username or all cache.
    """
    cache = TwitterCache()

    if username:
        cache.invalidate_all(username)
        console.print(f"[green]✓[/green] Cleared cache for @{username}")
    else:
        if typer.confirm("Clear all cache files?"):
            cache.clear_all()
            console.print("[green]✓[/green] Cleared all cache files")
        else:
            console.print("[yellow]Cache clear cancelled[/yellow]")


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
):
    """
    Start the web UI server.
    """
    from twitter_agent.api.main import run_server

    console.print(f"[cyan]Starting web server at http://{host}:{port}[/cyan]")
    console.print("[yellow]Press Ctrl+C to stop[/yellow]")
    run_server(host=host, port=port)


if __name__ == "__main__":
    app()
