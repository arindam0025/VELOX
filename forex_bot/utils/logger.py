"""
Structured logging setup using structlog and the standard library.

Log format, level, rotation, and destinations are driven entirely by
``forex_bot.config.CONFIG`` so no logging constants are duplicated elsewhere.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from typing import Any

import structlog
from structlog.types import FilteringBoundLogger

from forex_bot.config import CONFIG, AppConfig

_CONFIGURED: bool = False


def _coerce_log_level(name: str) -> int:
    """Map string log level to logging module constant."""

    level = getattr(logging, name.upper(), None)
    if not isinstance(level, int):
        return logging.INFO
    return level


def _build_timed_file_handler(cfg: AppConfig) -> TimedRotatingFileHandler:
    """Create a daily-rotating file handler under the configured log directory."""

    cfg.paths.log_dir.mkdir(parents=True, exist_ok=True)
    log_path = cfg.paths.log_dir / "forex_bot.log"
    handler = TimedRotatingFileHandler(
        filename=str(log_path),
        when=cfg.log_rotation_when,
        interval=cfg.log_rotation_interval,
        backupCount=cfg.log_backup_count,
        encoding="utf-8",
        utc=True,
    )
    handler.setLevel(_coerce_log_level(cfg.log_level))
    return handler


def _build_console_handler(cfg: AppConfig) -> logging.StreamHandler[Any]:
    """Create a stderr stream handler for development visibility."""

    handler: logging.StreamHandler[Any] = logging.StreamHandler(sys.stderr)
    handler.setLevel(_coerce_log_level(cfg.log_level))
    return handler


def _shared_processors() -> list[Any]:
    """Processors applied before handing off to stdlib logging formatters."""

    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def configure_logging(config: AppConfig | None = None) -> None:
    """
    Configure structlog and root logging once (idempotent).

    The rotating file uses JSON when ``log_json`` is True; the optional console
    stream uses a colored console renderer unless ``log_json`` forces JSON on
    all handlers.

    Args:
        config: Optional ``AppConfig`` override (defaults to ``CONFIG``).
    """

    global _CONFIGURED
    cfg = config or CONFIG

    if _CONFIGURED:
        return

    pre_chain = _shared_processors()

    structlog.configure(
        processors=pre_chain
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(_coerce_log_level(cfg.log_level))

    file_handler = _build_timed_file_handler(cfg)
    if cfg.log_json:
        file_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=pre_chain,
        )
    else:
        file_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=False),
            foreign_pre_chain=pre_chain,
        )
    file_handler.setFormatter(file_formatter)
    root.addHandler(file_handler)

    if cfg.log_to_console:
        console_handler = _build_console_handler(cfg)
        if cfg.log_json:
            console_formatter = structlog.stdlib.ProcessorFormatter(
                processor=structlog.processors.JSONRenderer(),
                foreign_pre_chain=pre_chain,
            )
        else:
            console_formatter = structlog.stdlib.ProcessorFormatter(
                processor=structlog.dev.ConsoleRenderer(colors=True),
                foreign_pre_chain=pre_chain,
            )
        console_handler.setFormatter(console_formatter)
        root.addHandler(console_handler)

    _CONFIGURED = True


def get_logger(name: str) -> FilteringBoundLogger:
    """
    Return a structlog logger bound to the given module name.

    Ensures ``configure_logging`` has been applied at least once.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A structlog bound logger with JSON or console rendering per config.
    """

    if not _CONFIGURED:
        configure_logging()
    return structlog.get_logger(name)
