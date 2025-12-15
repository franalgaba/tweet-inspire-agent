"""TwitterAPI.io client for fetching Twitter data."""

import json
import os
import re
from datetime import datetime
from typing import Optional

import httpx
from loguru import logger

from twitter_agent.models.schemas import Tweet, UserInfo
from twitter_agent.utils.cache import TwitterCache


class TwitterAPIError(Exception):
    """Custom exception for Twitter API errors."""

    pass


class TwitterAPIClient:
    """Client for interacting with TwitterAPI.io."""

    BASE_URL = "https://api.twitterapi.io"
    DEFAULT_TIMEOUT = 30.0
    MAX_PAGINATION_ATTEMPTS = 10

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache: Optional[TwitterCache] = None,
        use_cache: bool = True,
    ):
        """
        Initialize Twitter API client.

        Args:
            api_key: TwitterAPI.io API key. If not provided, will try to get from env.
            cache: TwitterCache instance (optional, creates default if use_cache=True)
            use_cache: Whether to use caching (default: True)
        """
        self.api_key = api_key or os.getenv("TWITTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "TwitterAPI.io API key is required. "
                "Set TWITTER_API_KEY environment variable or pass api_key parameter."
            )
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={"x-api-key": self.api_key},
            timeout=self.DEFAULT_TIMEOUT,
        )
        self.use_cache = use_cache
        if use_cache:
            self.cache = cache or TwitterCache()
        else:
            self.cache = None

    def get_user_info(
        self, username: str, use_cache: Optional[bool] = None
    ) -> UserInfo:
        """
        Get user information by username.

        Args:
            username: Twitter username (without @)
            use_cache: Override instance cache setting (optional)

        Returns:
            UserInfo object with user details

        Raises:
            TwitterAPIError: If API request fails
        """
        # Check cache first
        cache_enabled = use_cache if use_cache is not None else self.use_cache
        if cache_enabled and self.cache:
            cached_data = self.cache.get_user_info(username)
            if cached_data:
                logger.debug(f"Using cached user info for @{username}")
                return self._parse_user_info(cached_data, username)

        logger.debug(f"Fetching user info for @{username}")
        try:
            response = self._make_request(
                "/twitter/user/info", params={"userName": username}
            )
            data = response.json()
            user_data = self._extract_user_data(data)
            user_info = self._parse_user_info(user_data, username)

            # Cache the result
            if cache_enabled and self.cache:
                self.cache.set_user_info(username, user_data)

            logger.debug(
                f"Successfully fetched user info for @{username}: ID={user_info.user_id}"
            )
            return user_info
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error fetching user info for @{username}: {e.response.status_code}"
            )
            raise self._handle_user_info_error(e, username) from e
        except Exception as e:
            logger.exception(f"Unexpected error fetching user info for @{username}")
            raise TwitterAPIError(
                f"Unexpected error fetching user info: {str(e)}"
            ) from e

    def get_user_tweets(
        self,
        username: str,
        max_results: int = 100,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        use_cache: Optional[bool] = None,
        prefer_cache_only: bool = False,
    ) -> list[Tweet]:
        """
        Get user's historical tweets.

        Args:
            username: Twitter username (without @)
            max_results: Maximum number of tweets to fetch (default: 100)
            start_time: Start time in ISO 8601 format (optional, not currently used)
            end_time: End time in ISO 8601 format (optional, not currently used)
            use_cache: Override instance cache setting (optional)
            prefer_cache_only: If True, use cached tweets even if fewer than requested

        Returns:
            List of Tweet objects

        Raises:
            TwitterAPIError: If API request fails
        """
        # Check cache first - if cache has tweets, use all available cached tweets
        cache_enabled = use_cache if use_cache is not None else self.use_cache
        if cache_enabled and self.cache:
            # If prefer_cache_only, return all cached tweets even if fewer than requested
            cached_tweets = self.cache.get_tweets(
                username, max_results, return_all_if_available=prefer_cache_only
            )
            if cached_tweets:
                cached_count = len(cached_tweets)
                logger.info(
                    f"Using {cached_count} cached tweets for @{username} "
                    f"(requested: {max_results}, cache returned: {cached_count})"
                )
                # Return all cached tweets (cache.get_tweets already handles limiting)
                return [
                    self._parse_tweet(tweet_data, username)
                    for tweet_data in cached_tweets
                ]
            elif prefer_cache_only:
                # If prefer_cache_only and no cache, return empty rather than fetching
                logger.info(
                    f"No cached tweets found for @{username}, prefer_cache_only=True, returning empty list"
                )
                return []

        # If prefer_cache_only is True, don't fetch from API
        if prefer_cache_only:
            logger.info(
                f"prefer_cache_only=True and no cache available for @{username}, returning empty list"
            )
            return []

        try:
            logger.debug(f"Fetching tweets for @{username} using userName")
            tweet_data_list = self._fetch_tweets_with_pagination(username, max_results)

            if not tweet_data_list:
                self._handle_no_tweets_found(username)

            # Cache the result
            if cache_enabled and self.cache:
                self.cache.set_tweets(username, tweet_data_list)

            return [
                self._parse_tweet(tweet_data, username)
                for tweet_data in tweet_data_list
            ]
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error fetching tweets for @{username}: {e.response.status_code}"
            )
            raise TwitterAPIError(f"Failed to fetch tweets: {e.response.text}") from e
        except TwitterAPIError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error fetching tweets for @{username}")
            raise TwitterAPIError(f"Unexpected error fetching tweets: {str(e)}") from e

    def get_thread_context(self, tweet_id: str) -> Optional[list[Tweet]]:
        """
        Get thread context for a tweet (all tweets in the thread from the same author).

        Uses the thread_context endpoint first, then recursively follows reply chains
        to collect all tweets in the thread from the original author.

        Args:
            tweet_id: ID of the tweet to get thread context for

        Returns:
            List of Tweet objects in the thread from the same author, ordered chronologically, or None if not found
        """
        try:
            # First, get the original tweet to determine the author
            logger.debug(
                f"Fetching original tweet {tweet_id} to determine thread author"
            )
            original_tweet = self.get_tweet_by_id(tweet_id)
            thread_author_username = original_tweet.author_username

            if not thread_author_username:
                logger.warning(
                    f"Could not determine thread author for tweet {tweet_id} - author_username is empty"
                )
                return None

            logger.info(
                f"Building thread context for tweet {tweet_id} from author @{thread_author_username}"
            )

            # Start with the original tweet
            thread_tweets = []
            processed_tweet_ids = set()
            tweets_to_check = []

            # Try to get initial thread context from the API endpoint
            try:
                response = self._make_request(
                    "/twitter/tweet/thread_context", params={"tweetId": tweet_id}
                )
                data = response.json()
                self._validate_api_response(data)

                # Check for tweets in the response
                tweets_data = data.get("tweets", [])
                if not tweets_data:
                    tweets_data = data.get("thread", [])

                if tweets_data:
                    logger.info(
                        f"Thread context API returned {len(tweets_data)} initial tweets"
                    )
                    # Parse and filter tweets from the same author
                    authors_found = {}
                    tweets_with_missing_author = []
                    for tweet_data in tweets_data:
                        parsed_tweet = self._parse_tweet(tweet_data)
                        tweet_id_str = str(parsed_tweet.tweet_id)
                        author = parsed_tweet.author_username

                        # Check if author is missing or empty
                        if not author or author == "":
                            # Try to get author directly from tweet_data
                            raw_author = tweet_data.get("author", {})
                            raw_username = (
                                raw_author.get("userName")
                                if isinstance(raw_author, dict)
                                else None
                            )
                            if raw_username:
                                author = raw_username
                                logger.debug(
                                    f"Tweet {tweet_id_str} had missing author_username, found @{author} in raw data"
                                )
                            else:
                                tweets_with_missing_author.append(tweet_id_str)
                                logger.warning(
                                    f"Tweet {tweet_id_str} has no author information"
                                )
                                continue

                        # Track all authors found
                        if author not in authors_found:
                            authors_found[author] = []
                        authors_found[author].append(tweet_id_str)

                        # Check if this tweet is from the thread author (case-insensitive comparison)
                        if author.lower() == thread_author_username.lower():
                            if tweet_id_str not in processed_tweet_ids:
                                thread_tweets.append(parsed_tweet)
                                processed_tweet_ids.add(tweet_id_str)
                                tweets_to_check.append(tweet_id_str)
                                logger.debug(
                                    f"Added tweet {tweet_id_str} from @{author} (thread author)"
                                )
                        else:
                            logger.debug(
                                f"Skipping tweet {tweet_id_str} from @{author} (not thread author @{thread_author_username})"
                            )

                    if tweets_with_missing_author:
                        logger.warning(
                            f"Found {len(tweets_with_missing_author)} tweets with missing author information: {tweets_with_missing_author[:5]}"
                        )

                    # Log summary of authors found
                    logger.info(
                        f"Author breakdown in thread_context API: {[(author, len(tweet_ids)) for author, tweet_ids in authors_found.items()]}"
                    )
                    logger.info(
                        f"Found {len(thread_tweets)} tweets from @{thread_author_username} in thread_context API"
                    )
            except Exception as e:
                logger.debug(
                    f"Could not fetch from thread_context endpoint: {e}, will use recursive replies only"
                )

            # Ensure the original tweet is included
            tweet_id_str = str(tweet_id)
            if tweet_id_str not in processed_tweet_ids:
                thread_tweets.append(original_tweet)
                processed_tweet_ids.add(tweet_id_str)
                logger.debug(f"Added original tweet {tweet_id_str}")

            # If we didn't get any tweets from thread_context, start with the original tweet for recursive fetching
            if not tweets_to_check:
                tweets_to_check = [tweet_id_str]

            # Recursively fetch replies from the same author
            # This follows the reply chain: tweet1 -> reply1 -> reply2 -> reply3, etc.
            max_iterations = 50  # Safety limit to prevent infinite loops
            iteration = 0

            logger.info(
                f"Starting recursive reply chain traversal with {len(tweets_to_check)} tweets to check"
            )

            while tweets_to_check and iteration < max_iterations:
                iteration += 1
                current_tweet_id = tweets_to_check.pop(0)

                try:
                    # Get replies to the current tweet
                    logger.debug(
                        f"[Iteration {iteration}] Fetching replies for tweet {current_tweet_id} "
                        f"({len(tweets_to_check)} more tweets in queue)"
                    )
                    replies = self.get_tweet_replies(current_tweet_id, max_results=100)
                    logger.debug(
                        f"Found {len(replies)} total replies for tweet {current_tweet_id}"
                    )

                    if not replies:
                        logger.debug(f"No replies found for tweet {current_tweet_id}")
                        continue

                    # Filter replies from the same author and add them to the thread
                    found_thread_replies = 0
                    for reply in replies:
                        reply_id = str(reply.tweet_id)

                        # Skip if we've already processed this tweet
                        if reply_id in processed_tweet_ids:
                            logger.debug(f"Skipping already processed reply {reply_id}")
                            continue

                        # Only include replies from the thread author (case-insensitive)
                        if (
                            reply.author_username
                            and reply.author_username.lower()
                            == thread_author_username.lower()
                        ):
                            thread_tweets.append(reply)
                            processed_tweet_ids.add(reply_id)
                            tweets_to_check.append(
                                reply_id
                            )  # Add to queue to check its replies (recursive chain)
                            found_thread_replies += 1
                            logger.debug(
                                f"Added reply {reply_id} from @{reply.author_username} to thread (will check its replies next)"
                            )
                        else:
                            logger.debug(
                                f"Skipping reply {reply_id} from @{reply.author_username} "
                                f"(not thread author @{thread_author_username})"
                            )

                    if found_thread_replies > 0:
                        logger.info(
                            f"Found {found_thread_replies} thread replies from @{thread_author_username} "
                            f"for tweet {current_tweet_id} (added to queue for recursive checking)"
                        )
                    else:
                        logger.debug(
                            f"No thread replies found for tweet {current_tweet_id}"
                        )

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        logger.debug(
                            f"No replies found for tweet {current_tweet_id} (404)"
                        )
                    else:
                        logger.warning(
                            f"HTTP error fetching replies for tweet {current_tweet_id}: {e.response.status_code}"
                        )
                    # Continue with next tweet even if this one fails
                except Exception as e:
                    logger.warning(
                        f"Error fetching replies for tweet {current_tweet_id}: {e}"
                    )
                    # Continue with next tweet even if this one fails

            if iteration >= max_iterations:
                logger.warning(
                    f"Reached max iterations ({max_iterations}) while building thread context. "
                    f"Thread may be incomplete. Remaining tweets in queue: {len(tweets_to_check)}"
                )

            logger.info(
                f"Completed recursive reply chain traversal: {iteration} iterations, "
                f"{len(thread_tweets)} tweets found from @{thread_author_username}"
            )

            # Sort tweets by creation time to maintain chronological order
            # Tweets without timestamps go to the end (using a far future date)
            def sort_key(tweet: Tweet) -> datetime:
                if tweet.created_at:
                    return tweet.created_at
                # Use a far future date for tweets without timestamps
                return datetime(9999, 12, 31)

            thread_tweets.sort(key=sort_key)

            if len(thread_tweets) > 1:
                logger.info(
                    f"Found thread with {len(thread_tweets)} tweets from author @{thread_author_username} "
                    f"for tweet {tweet_id}"
                )
                return thread_tweets
            else:
                logger.debug(
                    f"Tweet {tweet_id} is not part of a thread (only 1 tweet from author)"
                )
                return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"No thread context found for tweet {tweet_id} (404)")
                return None
            logger.warning(
                f"HTTP error fetching thread context for tweet {tweet_id}: {e.response.status_code} - {e.response.text[:200]}"
            )
            return None
        except TwitterAPIError as e:
            logger.warning(
                f"Twitter API error fetching thread context for tweet {tweet_id}: {e}"
            )
            return None
        except Exception as e:
            logger.exception(
                f"Unexpected error fetching thread context for tweet {tweet_id}: {e}"
            )
            return None

    def get_article_by_tweet_id(self, tweet_id: str) -> Optional[dict]:
        """
        Get article data for a tweet if it links to an article.

        Args:
            tweet_id: ID of the tweet to check for article

        Returns:
            Dictionary with article data if found, None otherwise
            Structure: {
                "title": str,
                "preview_text": str,
                "contents": list[str],  # Full article text as list of paragraphs
                "author": dict,
                "created_at": str,
            }
        """
        try:
            response = self._make_request(
                "/twitter/article", params={"tweet_id": tweet_id}
            )
            data = response.json()

            self._validate_api_response(data)

            article_data = data.get("article")
            if not article_data:
                logger.debug(f"No article found for tweet {tweet_id}")
                return None

            # Extract article contents - combine all text elements
            contents_list = article_data.get("contents", [])
            article_text_parts = []
            for content_item in contents_list:
                if isinstance(content_item, dict):
                    text = content_item.get("text", "").strip()
                    if text:
                        article_text_parts.append(text)
                elif isinstance(content_item, str):
                    text = content_item.strip()
                    if text:
                        article_text_parts.append(text)

            article_text = "\n\n".join(article_text_parts)

            if not article_text:
                logger.debug(
                    f"Article found but no content extracted for tweet {tweet_id}"
                )
                return None

            logger.info(
                f"Found article for tweet {tweet_id}: {article_data.get('title', 'Untitled')}"
            )

            return {
                "title": article_data.get("title", ""),
                "preview_text": article_data.get("preview_text", ""),
                "contents": article_text_parts,
                "full_text": article_text,
                "author": article_data.get("author", {}),
                "created_at": article_data.get("createdAt"),
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"No article found for tweet {tweet_id} (404)")
                return None
            logger.warning(
                f"HTTP error fetching article for tweet {tweet_id}: {e.response.status_code}"
            )
            return None
        except Exception as e:
            logger.warning(f"Error fetching article for tweet {tweet_id}: {e}")
            return None

    def get_tweet_by_id(self, tweet_id: str) -> Tweet:
        """
        Get a single tweet by its ID.

        Args:
            tweet_id: ID of the tweet to fetch

        Returns:
            Tweet object with tweet details

        Raises:
            TwitterAPIError: If API request fails
        """
        logger.debug(f"Fetching tweet {tweet_id}")
        try:
            # Use /twitter/tweets endpoint with tweet_ids parameter
            response = self._make_request(
                "/twitter/tweets", params={"tweet_ids": tweet_id}
            )
            data = response.json()
            response_data = self._extract_response_data(data)

            tweets = response_data.get("tweets", [])
            if not tweets:
                raise TwitterAPIError(f"No tweet found with ID {tweet_id}")

            tweet_data = tweets[0]
            return self._parse_tweet(tweet_data)
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error fetching tweet {tweet_id}: {e.response.status_code}"
            )
            # Log full response for debugging
            try:
                error_detail = e.response.json()
                logger.debug(f"API error response: {error_detail}")
            except Exception:
                logger.debug(f"API error response (text): {e.response.text}")
            raise TwitterAPIError(f"Failed to fetch tweet: {e.response.text}") from e
        except Exception as e:
            logger.exception(f"Unexpected error fetching tweet {tweet_id}")
            raise TwitterAPIError(f"Unexpected error fetching tweet: {str(e)}") from e

    def get_tweet_replies(self, tweet_id: str, max_results: int = 100) -> list[Tweet]:
        """
        Get replies to a specific tweet.

        Args:
            tweet_id: ID of the tweet to get replies for
            max_results: Maximum number of replies to fetch

        Returns:
            List of Tweet objects representing replies
        """
        try:
            response = self._make_request(
                "/twitter/tweet/replies", params={"tweetId": tweet_id}
            )
            data = response.json()
            response_data = self._extract_response_data(data)

            tweet_data_list = response_data.get(
                "replies", response_data.get("tweets", [])
            )

            return [
                self._parse_tweet(tweet_data, referenced_tweet_id=tweet_id)
                for tweet_data in tweet_data_list[:max_results]
            ]
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error fetching replies for tweet {tweet_id}: {e.response.status_code}"
            )
            raise TwitterAPIError(f"Failed to fetch replies: {e.response.text}") from e
        except Exception as e:
            logger.exception(f"Unexpected error fetching replies for tweet {tweet_id}")
            raise TwitterAPIError(f"Unexpected error fetching replies: {str(e)}") from e

    def _make_request(
        self, endpoint: str, params: Optional[dict] = None
    ) -> httpx.Response:
        """
        Make an HTTP GET request to the API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            HTTP response

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        response = self.client.get(endpoint, params=params or {})
        response.raise_for_status()
        return response

    def _extract_response_data(self, data: dict) -> dict:
        """
        Extract data payload from API response (handles nested data structure).

        Args:
            data: Raw API response data

        Returns:
            Extracted data dictionary
        """
        return data.get("data", data)

    def _extract_user_data(self, data: dict) -> dict:
        """
        Extract user data from API response.

        Args:
            data: Raw API response data

        Returns:
            User data dictionary
        """
        response_data = self._extract_response_data(data)

        # Handle list responses
        if isinstance(response_data, list) and len(response_data) > 0:
            return response_data[0]

        return response_data

    def _extract_tweets_from_response(self, data: dict) -> list[dict]:
        """
        Extract tweets list from API response.

        Args:
            data: Raw API response data

        Returns:
            List of tweet data dictionaries
        """
        response_data = self._extract_response_data(data)
        return response_data.get("tweets", [])

    def _get_api_message(self, data: dict) -> str:
        """
        Extract message from API response (handles both 'msg' and 'message' fields).

        Args:
            data: Raw API response data

        Returns:
            Message string
        """
        return data.get("msg", data.get("message", ""))

    def _parse_user_info(self, user_data: dict, username: str) -> UserInfo:
        """
        Parse user data into UserInfo object.

        Args:
            user_data: User data dictionary from API
            username: Original username as fallback

        Returns:
            UserInfo object
        """
        return UserInfo(
            username=user_data.get("userName", username),
            user_id=user_data.get("id"),
            display_name=user_data.get("name"),
            bio=user_data.get("description"),
            followers_count=user_data.get("followers"),
            following_count=user_data.get("following"),
            tweet_count=user_data.get("statusesCount"),
        )

    def _parse_tweet(
        self,
        tweet_data: dict,
        author_username: Optional[str] = None,
        referenced_tweet_id: Optional[str] = None,
    ) -> Tweet:
        """
        Parse tweet data into Tweet object.

        Args:
            tweet_data: Raw tweet data from API
            author_username: Username to use if not in tweet data
            referenced_tweet_id: Tweet ID this tweet references (for replies/quotes)

        Returns:
            Tweet object
        """
        author = tweet_data.get("author", {})
        resolved_author_username = (
            author.get("userName") if author else author_username or ""
        )

        return Tweet(
            tweet_id=tweet_data.get("id", ""),
            text=tweet_data.get("text", ""),
            created_at=self._parse_datetime(tweet_data.get("createdAt")),
            author_username=resolved_author_username,
            like_count=tweet_data.get("likeCount"),
            retweet_count=tweet_data.get("retweetCount"),
            reply_count=tweet_data.get("replyCount"),
            quote_count=tweet_data.get("quoteCount"),
            is_reply=tweet_data.get("isReply", False),
            is_quote=bool(tweet_data.get("quoted_tweet")),
            referenced_tweet_id=referenced_tweet_id or tweet_data.get("inReplyToId"),
        )

    def _fetch_tweets_with_pagination(
        self, username: str, max_results: int
    ) -> list[dict]:
        """
        Fetch tweets with cursor-based pagination support.

        Args:
            username: Twitter username
            max_results: Maximum number of tweets to fetch

        Returns:
            List of tweet data dictionaries
        """
        params = {
            "userName": username,
            "includeReplies": False,
            "cursor": "",
        }

        all_tweets = []
        cursor = ""
        attempt = 0
        include_replies = False

        while len(all_tweets) < max_results and attempt < self.MAX_PAGINATION_ATTEMPTS:
            params["cursor"] = cursor
            params["includeReplies"] = include_replies

            logger.debug(f"Fetching tweets page {attempt + 1} with params: {params}")

            response = self._make_request("/twitter/user/last_tweets", params=params)
            data = response.json()

            self._validate_api_response(data)
            self._log_first_attempt_debug_info(data, attempt)

            tweet_data_list = self._extract_tweets_from_response(data)

            # Retry with replies if no tweets found on first attempt
            if not tweet_data_list and attempt == 0 and not include_replies:
                logger.info(
                    "No tweets found without replies, retrying with replies included..."
                )
                include_replies = True
                cursor = ""
                continue

            all_tweets.extend(tweet_data_list)

            # Check pagination - check both top level and nested data structure
            response_data = self._extract_response_data(data)
            has_next_page = data.get("has_next_page") or response_data.get(
                "has_next_page", False
            )
            next_cursor = data.get("next_cursor") or response_data.get(
                "next_cursor", ""
            )

            logger.info(
                f"Page {attempt + 1}: Got {len(tweet_data_list)} tweets, "
                f"total: {len(all_tweets)}/{max_results}, "
                f"has_next_page: {has_next_page}, "
                f"next_cursor: {next_cursor[:50] + '...' if next_cursor and len(next_cursor) > 50 else (next_cursor if next_cursor else 'empty')}"
            )

            # Check why we're stopping
            if len(all_tweets) >= max_results:
                logger.info(
                    f"✓ Reached max_results ({max_results}), stopping pagination"
                )
                break
            elif not has_next_page:
                logger.info(
                    f"✗ has_next_page is False (from top level: {data.get('has_next_page')}, from data: {response_data.get('has_next_page')}), stopping pagination"
                )
                break
            elif not next_cursor:
                logger.info(
                    f"✗ next_cursor is empty (from top level: {data.get('next_cursor')}, from data: {response_data.get('next_cursor')}), stopping pagination"
                )
                break

            cursor = next_cursor
            attempt += 1
            logger.info(f"→ Continuing to next page with cursor: {cursor[:50]}...")

        return all_tweets[:max_results]

    def _log_first_attempt_debug_info(self, data: dict, attempt: int) -> None:
        """
        Log debug information on first API call attempt.

        Args:
            data: API response data
            attempt: Current attempt number
        """
        if attempt != 0:
            return

        logger.debug(
            f"Full API response (first 2000 chars): {json.dumps(data, indent=2)[:2000]}"
        )

        status = data.get("status", "unknown")
        message = self._get_api_message(data)
        logger.info(f"API response status: {status}")
        logger.info(f"API response message: {message}")
        logger.info(f"Response keys: {list(data.keys())}")

        tweet_data_list = self._extract_tweets_from_response(data)
        logger.info(f"Tweets array length: {len(tweet_data_list)}")

        if tweet_data_list:
            logger.info(f"First tweet ID: {tweet_data_list[0].get('id', 'N/A')}")
            logger.info(
                f"First tweet text preview: {tweet_data_list[0].get('text', '')[:100]}"
            )
        else:
            logger.warning(
                f"No tweets found in response. Status: {status}, Message: {message}"
            )
            logger.debug(
                f"Full response structure: {json.dumps(data, indent=2)[:1000]}"
            )

    def _handle_no_tweets_found(self, username: str) -> None:
        """
        Handle case when no tweets are found - makes debug call and raises error.

        Args:
            username: Twitter username

        Raises:
            TwitterAPIError: Always raises with detailed error message
        """
        logger.debug("No tweets found, making final debug call with replies included")
        params = {"userName": username, "includeReplies": True, "cursor": ""}

        try:
            response = self._make_request("/twitter/user/last_tweets", params=params)
            debug_data = response.json()
            status = debug_data.get("status", "unknown")
            message = self._get_api_message(debug_data)
            tweet_count = len(self._extract_tweets_from_response(debug_data))

            logger.error(
                f"No tweets found - API status: {status}, "
                f"message: {message}, tweets in response: {tweet_count}"
            )
            raise TwitterAPIError(
                f"No tweets found for user @{username}. "
                f"API status: {status}, Message: {message}. "
                f"Tweets in response: {tweet_count}. "
                f"This might mean the user has no public tweets or the account is private."
            )
        except TwitterAPIError:
            raise
        except Exception as e:
            logger.exception("Error during debug call")
            raise TwitterAPIError(
                f"No tweets found for user @{username}. "
                f"This might mean the user has no public tweets or the account is private. "
                f"Debug error: {str(e)}"
            ) from e

    def _validate_api_response(self, data: dict) -> None:
        """
        Validate API response status.

        Args:
            data: API response data

        Raises:
            TwitterAPIError: If response indicates an error
        """
        status = data.get("status", "unknown")
        if status != "success":
            message = self._get_api_message(data) or "Unknown error"
            raise TwitterAPIError(f"API returned error status: {message}")

    def _handle_user_info_error(
        self, error: httpx.HTTPStatusError, username: str
    ) -> TwitterAPIError:
        """
        Create a user-friendly error message for user info failures.

        Args:
            error: HTTP error exception
            username: Username that was queried

        Returns:
            TwitterAPIError with helpful message
        """
        error_text = error.response.text
        status_code = error.response.status_code

        if status_code == 404:
            error_detail = error_text.lower()
            if "not found" in error_detail or '"detail"' in error_text:
                return TwitterAPIError(
                    f"User '@{username}' not found via TwitterAPI.io. "
                    f"This might mean:\n"
                    f"1. The username doesn't exist or has changed\n"
                    f"2. The account is private, suspended, or deleted\n"
                    f"3. The API endpoint format may be incorrect - please check TwitterAPI.io docs\n"
                    f"4. Your API key may not have access to this endpoint\n\n"
                    f"API response: {error_text}"
                )
            return TwitterAPIError(f"404 Not Found: {error_text}")

        return TwitterAPIError(
            f"Failed to fetch user info (HTTP {status_code}): {error_text}"
        )

    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
        """
        Parse datetime string from API response.

        Supports multiple formats:
        - ISO 8601 format (e.g., "2025-10-29T22:33:20Z")
        - Twitter format (e.g., "Wed Oct 29 22:33:20 +0000 2025")

        Args:
            dt_str: Datetime string

        Returns:
            Parsed datetime object or None if parsing fails
        """
        if not dt_str:
            return None

        # Try ISO 8601 format first
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

        # Try Twitter format: "Wed Oct 29 22:33:20 +0000 2025"
        try:
            return datetime.strptime(dt_str, "%a %b %d %H:%M:%S %z %Y")
        except (ValueError, AttributeError):
            logger.warning(f"Failed to parse datetime: {dt_str}")
            return None

    def invalidate_cache(self, username: str) -> None:
        """
        Invalidate cache for a username.

        Args:
            username: Twitter username
        """
        if self.cache:
            self.cache.invalidate_all(username)
            logger.info(f"Invalidated cache for @{username}")

    @staticmethod
    def extract_tweet_id_from_url(url: str) -> Optional[str]:
        """
        Extract tweet ID from a Twitter/X URL.

        Supports formats:
        - https://twitter.com/username/status/1234567890
        - https://x.com/username/status/1234567890
        - https://twitter.com/i/web/status/1234567890
        - https://x.com/i/web/status/1234567890

        Args:
            url: Twitter/X URL

        Returns:
            Tweet ID if found, None otherwise
        """
        # Pattern to match tweet IDs in URLs
        patterns = [
            r"(?:twitter\.com|x\.com)/(?:\w+/)?status/(\d+)",
            r"/status/(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                tweet_id = match.group(1)
                logger.debug(f"Extracted tweet ID {tweet_id} from URL: {url}")
                return tweet_id

        logger.warning(f"Could not extract tweet ID from URL: {url}")
        return None

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
