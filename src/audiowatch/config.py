"""Configuration management for AudioWatch.

Loads configuration from YAML files and environment variables using Pydantic.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScraperConfig(BaseModel):
    """Configuration for the Head-Fi scraper."""

    poll_interval_minutes: int = Field(
        default=5,
        ge=1,
        le=60,
        description="How often to check for new listings (1-60 minutes)",
    )
    initial_scrape_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="How far back to scrape on first run (days)",
    )
    initial_max_pages: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum pages per category for initial scrape",
    )
    scheduled_max_pages: int = Field(
        default=2,
        ge=1,
        le=20,
        description="Maximum pages per category for scheduled scrapes (lower since they run frequently)",
    )
    rate_limit_delay_seconds: float = Field(
        default=2.0,
        ge=0.5,
        le=30.0,
        description="Delay between page requests to avoid rate limiting",
    )
    categories: list[str] = Field(
        default_factory=lambda: [
            "headphones",
            "amplification",
            "source-components",
            "cables-accessories",
            "media",
        ],
        description="Which Head-Fi categories to monitor",
    )
    headless: bool = Field(
        default=True,
        description="Run browser in headless mode",
    )
    timeout_seconds: int = Field(
        default=30,
        ge=10,
        le=120,
        description="Page load timeout in seconds",
    )


class DatabaseConfig(BaseModel):
    """Configuration for the DuckDB database."""

    path: Path = Field(
        default=Path("./data/audiowatch.db"),
        description="Path to the DuckDB database file",
    )

    @field_validator("path", mode="before")
    @classmethod
    def expand_path(cls, v: Any) -> Path:
        """Expand user home directory and make path absolute."""
        if isinstance(v, str):
            v = Path(v)
        return Path(os.path.expanduser(str(v))).resolve()


class EmailConfig(BaseModel):
    """Configuration for email notifications."""

    enabled: bool = Field(default=False, description="Enable email notifications")
    smtp_server: str = Field(default="smtp.gmail.com", description="SMTP server address")
    smtp_port: int = Field(default=587, description="SMTP server port")
    sender_email: str = Field(default="", description="Sender email address")
    sender_password: str = Field(default="", description="Sender email password or app password")
    recipient_email: str = Field(default="", description="Recipient email address")
    use_tls: bool = Field(default=True, description="Use TLS encryption")


class DiscordConfig(BaseModel):
    """Configuration for Discord notifications."""

    enabled: bool = Field(default=False, description="Enable Discord notifications")
    webhook_url: str = Field(default="", description="Discord webhook URL")


class NotificationsConfig(BaseModel):
    """Configuration for all notification channels."""

    email: EmailConfig = Field(default_factory=EmailConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)


class RuleFilters(BaseModel):
    """Optional filters specific to a watch rule.

    These override or extend global filters for this specific rule.
    """

    listing_types: list[str] | None = Field(
        default=None,
        description="Override: only match these listing types for this rule",
    )
    ships_to: list[str] | None = Field(
        default=None,
        description="Override: only match listings shipping to these regions",
    )
    exclude_status: list[str] | None = Field(
        default=None,
        description="Override: exclude these statuses for this rule",
    )
    min_seller_reputation: int | None = Field(
        default=None,
        ge=0,
        description="Override: minimum seller reputation for this rule",
    )


class WatchRule(BaseModel):
    """A single watch rule for matching listings."""

    name: str = Field(..., description="Human-readable name for this rule")
    expression: str = Field(..., description="Boolean expression to match listings")
    notify_via: list[str] = Field(
        default_factory=lambda: ["discord"],
        description="Notification channels to use (email, discord)",
    )
    enabled: bool = Field(default=True, description="Whether this rule is active")

    # Per-rule category filtering
    categories: list[str] | None = Field(
        default=None,
        description="Only match listings in these categories (None = all categories)",
    )

    # Per-rule filters (override global filters)
    filters: RuleFilters | None = Field(
        default=None,
        description="Rule-specific filters that override global filters",
    )

    @field_validator("notify_via", mode="before")
    @classmethod
    def validate_notify_channels(cls, v: Any) -> list[str]:
        """Validate notification channels."""
        if isinstance(v, str):
            v = [v]
        valid_channels = {"email", "discord"}
        for channel in v:
            if channel not in valid_channels:
                raise ValueError(f"Invalid notification channel: {channel}")
        return v


class GlobalFilters(BaseModel):
    """Global filters applied to all watch rules.

    These filters are automatically AND-ed with every watch rule expression.
    Use this to set baseline criteria like listing type or shipping regions.
    """

    listing_types: list[str] = Field(
        default_factory=list,
        description="Only match these listing types (e.g., ['For Sale', 'For Sale/Trade']). Empty = all types.",
    )
    exclude_listing_types: list[str] = Field(
        default_factory=list,
        description="Listing types to exclude (e.g., ['Want To Buy'])",
    )
    ships_to: list[str] = Field(
        default_factory=list,
        description="Only match listings that ship to these regions",
    )
    exclude_status: list[str] = Field(
        default_factory=lambda: ["sold", "expired", "deleted"],
        description="Listing statuses to exclude (sold, expired, deleted)",
    )
    min_seller_reputation: int | None = Field(
        default=None,
        ge=0,
        description="Minimum seller reputation score",
    )


class DashboardConfig(BaseModel):
    """Configuration for the Streamlit dashboard."""

    port: int = Field(default=8501, ge=1024, le=65535, description="Dashboard port")
    host: str = Field(default="localhost", description="Dashboard host")


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="console", description="Log format (console or json)")
    file: Path | None = Field(default=None, description="Optional log file path")

    @field_validator("level", mode="before")
    @classmethod
    def validate_level(cls, v: Any) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if isinstance(v, str):
            v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}")
        return v


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_prefix="AUDIOWATCH_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    scraper: ScraperConfig = Field(default_factory=ScraperConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    watch_rules: list[WatchRule] = Field(default_factory=list)
    global_filters: GlobalFilters = Field(default_factory=GlobalFilters)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_yaml_config(config_path: Path) -> dict[str, Any]:
    """Load configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Dictionary containing the configuration.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        yaml.YAMLError: If the YAML is invalid.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return config or {}


def expand_env_vars(config: dict[str, Any]) -> dict[str, Any]:
    """Recursively expand environment variables in configuration values.

    Supports ${VAR_NAME} syntax for environment variable expansion.

    Args:
        config: Configuration dictionary.

    Returns:
        Configuration with environment variables expanded.
    """

    def expand_value(value: Any) -> Any:
        if isinstance(value, str):
            # Handle ${VAR_NAME} syntax
            import re

            pattern = r"\$\{([^}]+)\}"
            matches = re.findall(pattern, value)
            for var_name in matches:
                env_value = os.environ.get(var_name, "")
                value = value.replace(f"${{{var_name}}}", env_value)
            return value
        elif isinstance(value, dict):
            return {k: expand_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [expand_value(item) for item in value]
        return value

    return expand_value(config)


def load_settings(config_path: Path | None = None) -> Settings:
    """Load application settings from YAML file and environment variables.

    Environment variables take precedence over YAML configuration.

    Args:
        config_path: Optional path to YAML config file. If not provided,
                    looks for config.yaml in the current directory.

    Returns:
        Validated Settings object.
    """
    # Default config path
    if config_path is None:
        config_path = Path("config.yaml")

    # Load YAML config if it exists
    yaml_config: dict[str, Any] = {}
    if config_path.exists():
        yaml_config = load_yaml_config(config_path)
        yaml_config = expand_env_vars(yaml_config)

    # Create settings (env vars will override YAML)
    return Settings(**yaml_config)


# Global settings instance (lazy-loaded)
_settings: Settings | None = None


def get_settings(config_path: Path | None = None, reload: bool = False) -> Settings:
    """Get the global settings instance.

    Args:
        config_path: Optional path to config file for initial load.
        reload: Force reload of settings.

    Returns:
        The global Settings instance.
    """
    global _settings
    if _settings is None or reload:
        _settings = load_settings(config_path)
    return _settings
