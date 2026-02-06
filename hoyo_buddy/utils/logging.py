from __future__ import annotations

import inspect
import logging
import sys

from loguru import logger

from hoyo_buddy.config import CONFIG

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

    logger.add(log_dir, rotation="2 hours", retention="1 week", level="DEBUG")
