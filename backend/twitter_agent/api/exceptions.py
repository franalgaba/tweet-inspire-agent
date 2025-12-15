"""Custom exceptions for the web API."""


class TwitterAgentError(Exception):
    """Base exception for Twitter Agent errors."""

    pass


class ConfigurationError(TwitterAgentError):
    """Raised when there's a configuration error."""

    pass


class TwitterAPIError(TwitterAgentError):
    """Raised when there's an error with the Twitter API."""

    pass


class OllamaError(TwitterAgentError):
    """Raised when there's an error with Ollama."""

    pass


class PerplexityError(TwitterAgentError):
    """Raised when there's an error with Perplexity API."""

    pass

