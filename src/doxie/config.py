from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseModel):
    """Application-specific configuration values."""

    name: str = "Doxie"
    env: str = "development"
    debug: bool = True
    port: int = 8000
    secret_key: Optional[str] = None
    log_level: str = "INFO"
    # Transport settings for FastMCP: "stdio" (default), "http", or "sse"
    transport: Literal["stdio", "http", "sse"] = "stdio"
    host: str = "127.0.0.1"


class DatabaseConfig(BaseModel):
    """Database configuration values."""

    # Default to docker-compose service credentials
    url: str = "postgresql+psycopg://user:password@db:5432/doxie"


class ConfluenceConfig(BaseModel):
    """Confluence connector configuration values."""

    base_url: Optional[str] = None
    username: Optional[str] = None
    token: Optional[str] = None  # API token/password
    space: Optional[str] = None
    spaces: Optional[str] = None  # Comma-separated space keys from env, e.g. "DOCS, ENG"
    cloud: bool = True
    verify_ssl: bool = True


class GitHubConfig(BaseModel):
    """GitHub connector configuration values."""

    token: Optional[str] = None  # Personal Access Token (optional for public repos)
    api_base_url: str = "https://api.github.com"
    web_base_url: str = "https://github.com"
    raw_base_url: str = "https://raw.githubusercontent.com"


class Settings(BaseSettings):
    """Top-level settings loaded from environment variables and .env only."""

    model_config = SettingsConfigDict(
        env_prefix="DOXIE_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    app: AppConfig = AppConfig()
    database: DatabaseConfig = DatabaseConfig()
    confluence: ConfluenceConfig = ConfluenceConfig()
    github: GitHubConfig = GitHubConfig()


def load_settings() -> Settings:
    """Load settings from environment variables and .env only."""
    return Settings()  # type: ignore[call-arg]
