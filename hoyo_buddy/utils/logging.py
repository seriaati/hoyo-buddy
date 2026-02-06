from __future__ import annotations

import inspect
import logging
import random
import sys
from typing import TYPE_CHECKING

from loguru import logger

from hoyo_buddy.config import CONFIG

if TYPE_CHECKING:
    from typing import Any

__all__ = ("setup_logging",)


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _production_log_filter(record: dict[str, Any]) -> bool:
    """Filter out high-volume, low-value logs in production.

    Removes:
    - Cache hit/miss DEBUG logs (already tracked in Redis metrics)
    - Routine SELECT query logs (keep INSERT/UPDATE/DELETE for auditing)
    - Routine API request logs (duplicated in external libraries)
    - 90% of supporter ID logs (sample to reduce volume)
    """
    message = record["message"]

    if record["level"].name == "DEBUG":
        # Filter cache operations
        if "Cache hit" in message or "Cache miss" in message:
            return False

        # Filter SELECT queries (keep INSERT/UPDATE/DELETE)
        if "execute_query" in message and "SELECT" in message:
            return False

        # Filter routine API request logs
        if "Fetching text from" in message or "_request_hook" in message:
            return False

        # Sample supporter ID logs (10% only)
        if "Supporter IDs:" in message:
            return random.random() < 0.1

    return True


def setup_logging(log_dir: str) -> None:
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if CONFIG.is_dev else "INFO")

    loggers = ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi", "asyncio", "starlette")

    for logger_name in loggers:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = []
        logging_logger.propagate = True

    if CONFIG.is_dev:
        logging.getLogger("tortoise").setLevel(logging.DEBUG)
    else:
        logger.disable("hoyo_buddy.db.models.base")
        logger.disable("aiohttp.web_log")

    logging.getLogger("discord.app_commands.tree").addFilter(
        lambda record: "Ignoring exception in autocomplete for" not in record.getMessage()
    )
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)

    add_kwargs: dict[str, Any] = {
        "rotation": CONFIG.log_rotation_size,
        "retention": CONFIG.log_retention_count,
        "compression": CONFIG.log_compression,
        "level": CONFIG.log_level,
        "serialize": CONFIG.log_structured,
        "enqueue": True,
        "diagnose": CONFIG.is_dev,
        "backtrace": CONFIG.is_dev,
    }

    if CONFIG.log_structured:
        add_kwargs["format"] = CONFIG.log_format

    if not CONFIG.is_dev:
        add_kwargs["filter"] = _production_log_filter

    logger.add(log_dir, **add_kwargs)
