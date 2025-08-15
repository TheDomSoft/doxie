"""Configuration loading utilities using pydantic-settings.

This module exposes the Settings class and a loader that merges YAML and environment
variables. Environment variables take precedence over YAML values.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Literal

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_yaml(path: Path) -> Dict[str, Any]:
    """Read a YAML file and return a dict. Missing file returns empty dict.

    Parameters
    ----------
    path: Path
        Path to the YAML file.
    """
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return data


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
    cloud: bool = True
    verify_ssl: bool = True


class Settings(BaseSettings):
    """Top-level settings loaded from YAML, env and .env.

    Uses a custom YAML source with lower priority than environment variables.
    """

    model_config = SettingsConfigDict(
        env_prefix="DOXIE_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    app: AppConfig = AppConfig()
    database: DatabaseConfig = DatabaseConfig()
    confluence: ConfluenceConfig = ConfluenceConfig()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,  # type: ignore[unused-argument]
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """Insert YAML settings as a low-priority source (after init, before env)."""

        # Use the built-in YamlConfigSettingsSource for v2 API
        from pydantic_settings import YamlConfigSettingsSource  # type: ignore

        config_path = Path(
            __import__("os").environ.get("DOXIE_CONFIG_PATH", "config/settings.yaml")
        )
        yaml_source = YamlConfigSettingsSource(settings_cls, yaml_file=config_path)

        # Ensure env and .env override YAML (YAML lowest precedence)
        return (init_settings, env_settings, dotenv_settings, yaml_source, file_secret_settings)


def load_settings(config_path: Optional[Path | str] = None) -> Settings:
    """Load settings, optionally from a specific YAML path.

    If ``config_path`` is given, it is used as the YAML source path.
    Environment variables still take precedence.
    """
    if config_path is not None:
        # Temporarily override discovery for a single call
        from os import environ

        environ["DOXIE_CONFIG_PATH"] = str(config_path)
    return Settings()  # type: ignore[call-arg]
