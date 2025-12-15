"""Configuration settings for the web API."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    twitter_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_api_key: str | None = None
    perplexity_api_key: str | None = None
    content_dir: str = "content"
    frontend_url: str | None = None
    allow_all_origins: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

