"""Utility for extracting article content from URLs."""

import re
from typing import Optional
from urllib.parse import urlparse

import httpx
from loguru import logger

try:
    from readability import Readability
    from lxml import html

    READABILITY_AVAILABLE = True
except ImportError:
    READABILITY_AVAILABLE = False


class ArticleExtractor:
    """Extract article content from URLs."""

    def __init__(self, timeout: float = 10.0):
        """
        Initialize article extractor.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)

    def extract_urls_from_text(self, text: str) -> list[str]:
        """
        Extract URLs from text.

        Args:
            text: Text containing URLs

        Returns:
            List of URLs found in the text
        """
        # Pattern to match URLs
        url_pattern = r"https?://[^\s]+"
        urls = re.findall(url_pattern, text)
        # Clean up URLs (remove trailing punctuation that's not part of URL)
        cleaned_urls = []
        for url in urls:
            # Remove trailing punctuation that's likely not part of URL
            url = url.rstrip(".,;:!?)")
            cleaned_urls.append(url)
        return cleaned_urls

    def is_article_url(self, url: str) -> bool:
        """
        Check if URL is likely an article/blog post.

        Args:
            url: URL to check

        Returns:
            True if URL appears to be an article
        """
        parsed = urlparse(url)
        path = parsed.path.lower()

        # Common article/blog patterns
        article_indicators = [
            "/article/",
            "/post/",
            "/blog/",
            "/news/",
            "/story/",
            "/2024/",
            "/2025/",
            "/p/",  # Medium posts
            ".html",
            ".htm",
        ]

        # Exclude social media and common non-article domains
        excluded_domains = [
            "twitter.com",
            "x.com",
            "youtube.com",
            "youtu.be",
            "instagram.com",
            "tiktok.com",
            "linkedin.com",
            "facebook.com",
            "reddit.com",
            "github.com",
        ]

        domain = parsed.netloc.lower()

        # Check if domain is excluded
        if any(excluded in domain for excluded in excluded_domains):
            return False

        # Check if path suggests an article
        if any(indicator in path for indicator in article_indicators):
            return True

        # If path has date-like pattern (YYYY/MM/DD or YYYY-MM-DD), likely an article
        date_pattern = r"/\d{4}[/-]\d{1,2}[/-]\d{1,2}/"
        if re.search(date_pattern, path):
            return True

        # If path is mostly empty (just domain), probably not an article
        if len(path) <= 1:
            return False

        # Default: treat as potential article if it's not clearly excluded
        return True

    def extract_article_content(self, url: str) -> Optional[str]:
        """
        Extract article content from URL.

        Args:
            url: URL to fetch article from

        Returns:
            Article content text, or None if extraction failed
        """
        try:
            logger.debug(f"Fetching article content from: {url}")
            response = self.client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type:
                logger.debug(f"URL does not contain HTML content: {content_type}")
                return None

            html_content = response.text

            if READABILITY_AVAILABLE:
                # Use readability-lxml for better extraction
                try:
                    doc = html.fromstring(html_content)
                    readable_article = Readability(doc)
                    article_text = readable_article.text()
                    if article_text and len(article_text.strip()) > 100:
                        logger.info(f"Extracted {len(article_text)} characters from article")
                        return article_text.strip()
                except Exception as e:
                    logger.warning(f"Readability extraction failed: {e}, trying fallback")

            # Fallback: basic extraction using regex
            # Remove script and style tags
            cleaned_html = re.sub(
                r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE
            )
            cleaned_html = re.sub(
                r"<style[^>]*>.*?</style>", "", cleaned_html, flags=re.DOTALL | re.IGNORECASE
            )

            # Extract text from common article tags
            article_patterns = [
                r"<article[^>]*>(.*?)</article>",
                r"<main[^>]*>(.*?)</main>",
                r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*post[^"]*"[^>]*>(.*?)</div>',
            ]

            for pattern in article_patterns:
                matches = re.findall(pattern, cleaned_html, re.DOTALL | re.IGNORECASE)
                if matches:
                    # Extract text from HTML
                    text_content = re.sub(r"<[^>]+>", " ", " ".join(matches))
                    text_content = re.sub(r"\s+", " ", text_content).strip()
                    if len(text_content) > 100:
                        logger.info(f"Extracted {len(text_content)} characters using fallback method")
                        return text_content

            # Last resort: extract all text from body
            body_match = re.search(r"<body[^>]*>(.*?)</body>", cleaned_html, re.DOTALL | re.IGNORECASE)
            if body_match:
                text_content = re.sub(r"<[^>]+>", " ", body_match.group(1))
                text_content = re.sub(r"\s+", " ", text_content).strip()
                if len(text_content) > 100:
                    logger.info(f"Extracted {len(text_content)} characters from body")
                    return text_content

            logger.warning(f"Could not extract meaningful content from: {url}")
            return None

        except httpx.HTTPError as e:
            logger.warning(f"HTTP error fetching article: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error extracting article content: {e}")
            return None

    def extract_article_from_tweet(self, tweet_text: str) -> Optional[str]:
        """
        Extract article content from URLs found in tweet text.

        Args:
            tweet_text: Tweet text that may contain URLs

        Returns:
            Article content if URL found and extracted, None otherwise
        """
        urls = self.extract_urls_from_text(tweet_text)
        if not urls:
            return None

        # Try each URL until we find an article
        for url in urls:
            if self.is_article_url(url):
                content = self.extract_article_content(url)
                if content:
                    return content

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

