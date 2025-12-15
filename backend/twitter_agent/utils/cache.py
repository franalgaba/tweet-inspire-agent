"""Caching utilities for Twitter API responses."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger


class TwitterCache:
    """File-based cache for Twitter API responses."""

    def __init__(self, cache_dir: Optional[str] = None, ttl_hours: int = 24):
        """
        Initialize Twitter cache.

        Args:
            cache_dir: Directory to store cache files (default: .cache/twitter-agent)
            ttl_hours: Time-to-live for cache entries in hours (default: 24)
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            # Default to .cache/twitter-agent in user's home or project root
            project_root = Path.cwd()
            self.cache_dir = project_root / ".cache" / "twitter-agent"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = ttl_hours
        logger.debug(f"Cache directory: {self.cache_dir}, TTL: {ttl_hours} hours")

    def _get_user_info_path(self, username: str) -> Path:
        """Get cache file path for user info."""
        safe_username = username.lower().replace("@", "")
        return self.cache_dir / f"user_info_{safe_username}.json"

    def _get_tweets_path(self, username: str) -> Path:
        """Get cache file path for tweets."""
        safe_username = username.lower().replace("@", "")
        return self.cache_dir / f"tweets_{safe_username}.json"

    def _is_expired(self, cache_data: dict) -> bool:
        """
        Check if cache entry is expired.

        Args:
            cache_data: Cached data dictionary with 'cached_at' timestamp

        Returns:
            True if expired, False otherwise
        """
        if "cached_at" not in cache_data:
            return True
        
        cached_at = datetime.fromisoformat(cache_data["cached_at"])
        expiry_time = cached_at + timedelta(hours=self.ttl_hours)
        return datetime.now() > expiry_time

    def get_user_info(self, username: str) -> Optional[dict]:
        """
        Get cached user info.

        Args:
            username: Twitter username

        Returns:
            Cached user info dict or None if not found/expired
        """
        cache_path = self._get_user_info_path(username)
        if not cache_path.exists():
            return None

        try:
            cache_data = json.loads(cache_path.read_text())
            if self._is_expired(cache_data):
                logger.debug(f"Cache expired for user info: @{username}")
                return None
            
            logger.debug(f"Cache hit for user info: @{username}")
            return cache_data.get("data")
        except Exception as e:
            logger.warning(f"Error reading cache for user info @{username}: {e}")
            return None

    def set_user_info(self, username: str, user_info: dict) -> None:
        """
        Cache user info.

        Args:
            username: Twitter username
            user_info: User info dictionary to cache
        """
        cache_path = self._get_user_info_path(username)
        cache_data = {
            "username": username,
            "cached_at": datetime.now().isoformat(),
            "data": user_info,
        }
        
        try:
            cache_path.write_text(json.dumps(cache_data, indent=2, default=str))
            logger.debug(f"Cached user info for @{username}")
        except Exception as e:
            logger.warning(f"Error writing cache for user info @{username}: {e}")

    def get_tweets(self, username: str, max_results: Optional[int] = None, return_all_if_available: bool = False) -> Optional[list[dict]]:
        """
        Get cached tweets.

        Args:
            username: Twitter username
            max_results: Maximum number of tweets to return (None = all cached)
            return_all_if_available: If True, return all cached tweets even if fewer than max_results
                                   (False = return None if cache has less than 80% of requested)

        Returns:
            List of cached tweet dicts or None if not found/expired/insufficient
        """
        cache_path = self._get_tweets_path(username)
        if not cache_path.exists():
            return None

        try:
            cache_data = json.loads(cache_path.read_text())
            if self._is_expired(cache_data):
                logger.debug(f"Cache expired for tweets: @{username}")
                return None
            
            tweets = cache_data.get("data", [])
            
            # If max_results is None or return_all_if_available is True, return all cached tweets
            if max_results is None or return_all_if_available:
                logger.debug(f"Cache hit for tweets: @{username} (returning all {len(tweets)} cached tweets)")
                return tweets
            
            # If max_results is specified and cache has fewer tweets, return None to fetch more
            # But only if the gap is significant (more than 20% difference)
            if len(tweets) < max_results:
                if len(tweets) < max_results * 0.8:  # Less than 80% of requested
                    logger.debug(
                        f"Cache has {len(tweets)} tweets but {max_results} requested, "
                        f"fetching from API for @{username}"
                    )
                    return None
                else:
                    # Cache has at least 80% of requested, use it
                    logger.debug(
                        f"Cache has {len(tweets)} tweets ({(len(tweets)/max_results)*100:.1f}% of {max_results} requested), "
                        f"using cached tweets for @{username}"
                    )
                    return tweets
            
            # Limit to requested amount if cached tweets exceed it
            if len(tweets) > max_results:
                tweets = tweets[:max_results]
            
            logger.debug(f"Cache hit for tweets: @{username} ({len(tweets)} tweets)")
            return tweets
        except Exception as e:
            logger.warning(f"Error reading cache for tweets @{username}: {e}")
            return None

    def set_tweets(self, username: str, tweets: list[dict]) -> None:
        """
        Cache tweets.

        Args:
            username: Twitter username
            tweets: List of tweet dictionaries to cache
        """
        cache_path = self._get_tweets_path(username)
        cache_data = {
            "username": username,
            "cached_at": datetime.now().isoformat(),
            "data": tweets,
        }
        
        try:
            cache_path.write_text(json.dumps(cache_data, indent=2, default=str))
            logger.debug(f"Cached {len(tweets)} tweets for @{username}")
        except Exception as e:
            logger.warning(f"Error writing cache for tweets @{username}: {e}")

    def invalidate_user_info(self, username: str) -> None:
        """
        Invalidate cached user info.

        Args:
            username: Twitter username
        """
        cache_path = self._get_user_info_path(username)
        if cache_path.exists():
            cache_path.unlink()
            logger.debug(f"Invalidated cache for user info: @{username}")

    def invalidate_tweets(self, username: str) -> None:
        """
        Invalidate cached tweets.

        Args:
            username: Twitter username
        """
        cache_path = self._get_tweets_path(username)
        if cache_path.exists():
            cache_path.unlink()
            logger.debug(f"Invalidated cache for tweets: @{username}")

    def invalidate_all(self, username: str) -> None:
        """
        Invalidate all cache for a username.

        Args:
            username: Twitter username
        """
        self.invalidate_user_info(username)
        self.invalidate_tweets(username)

    def clear_all(self) -> None:
        """Clear all cache files."""
        if not self.cache_dir.exists():
            return
        
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        
        logger.info(f"Cleared {count} cache files")

    def get_cache_info(self, username: str) -> dict:
        """
        Get cache information for a username.

        Args:
            username: Twitter username

        Returns:
            Dictionary with cache status information
        """
        info = {
            "username": username,
            "user_info_cached": False,
            "tweets_cached": False,
            "user_info_age_hours": None,
            "tweets_age_hours": None,
            "tweets_count": 0,
        }

        # Check user info cache
        user_info_path = self._get_user_info_path(username)
        if user_info_path.exists():
            try:
                cache_data = json.loads(user_info_path.read_text())
                cached_at = datetime.fromisoformat(cache_data["cached_at"])
                age = (datetime.now() - cached_at).total_seconds() / 3600
                info["user_info_cached"] = True
                info["user_info_age_hours"] = round(age, 2)
            except Exception:
                pass

        # Check tweets cache
        tweets_path = self._get_tweets_path(username)
        if tweets_path.exists():
            try:
                cache_data = json.loads(tweets_path.read_text())
                cached_at = datetime.fromisoformat(cache_data["cached_at"])
                age = (datetime.now() - cached_at).total_seconds() / 3600
                tweets = cache_data.get("data", [])
                info["tweets_cached"] = True
                info["tweets_age_hours"] = round(age, 2)
                info["tweets_count"] = len(tweets)
            except Exception:
                pass

        return info

