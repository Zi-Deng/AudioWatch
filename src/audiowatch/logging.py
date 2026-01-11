"""Logging configuration for AudioWatch using structlog.

Provides structured logging with console and JSON output formats.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from structlog.types import Processor

if TYPE_CHECKING:
    from audiowatch.config import LoggingConfig


def setup_logging(config: LoggingConfig | None = None) -> None:
    """Configure structlog and standard library logging.

    Args:
        config: Optional logging configuration. If None, uses defaults.
    """
    if config is None:
        from audiowatch.config import get_settings

        config = get_settings().logging

    # Set up standard library logging level
    log_level = getattr(logging, config.level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Build processor chain based on output format
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if config.format == "json":
        # JSON output for production/log aggregation
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Console output for development
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set up file logging if configured
    if config.file is not None:
        _setup_file_logging(config.file, log_level)


def _setup_file_logging(file_path: Path, level: int) -> None:
    """Set up file-based logging.

    Args:
        file_path: Path to the log file.
        level: Logging level.
    """
    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Create file handler
    file_handler = logging.FileHandler(file_path)
    file_handler.setLevel(level)

    # Use JSON format for file logs
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    # Add handler to root logger
    logging.getLogger().addHandler(file_handler)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Optional logger name. If None, uses the caller's module name.

    Returns:
        A structlog BoundLogger instance.
    """
    return structlog.get_logger(name)


# Convenience function for getting a logger with context
def bind_context(**kwargs: object) -> None:
    """Bind context variables that will be included in all subsequent log messages.

    Args:
        **kwargs: Key-value pairs to bind to the logging context.
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()


__all__ = [
    "setup_logging",
    "get_logger",
    "bind_context",
    "clear_context",
]
