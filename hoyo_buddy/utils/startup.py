from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

import sentry_sdk
from loguru import logger
from sentry_sdk.integrations.logging import LoggingIntegration

from hoyo_buddy.config import CONFIG
from hoyo_buddy.logging import InterceptHandler
from hoyo_buddy.utils.misc import get_project_version, should_ignore_error

__all__ = ("setup_async_event_loop", "setup_logging", "setup_sentry", "wrap_task_factory")

_tasks_set: set[asyncio.Task[Any] | asyncio.Future[Any]] = set()


def wrap_task_factory() -> None:
    loop = asyncio.get_running_loop()
    original_factory = loop.get_task_factory()

    async def coro_wrapper(coro: asyncio._CoroutineLike[Any], coro_name: str | None = None) -> Any:
        try:
            return await coro
        except Exception as e:
            if not should_ignore_error(e):
                name = coro_name or getattr(coro, "__name__", str(coro))
                if CONFIG.sentry:
                    logger.warning(f"Error in task {name!r}: {e}, capturing exception")
                    sentry_sdk.capture_exception(e)
                else:
                    logger.exception(f"Error in task {name!r}: {e}")

            # Still raise the exception, so errors like `StopAsyncIteration` can work properly
            raise

    def new_factory(
        loop: asyncio.AbstractEventLoop, coro: asyncio._CoroutineLike[Any], **kwargs
    ) -> asyncio.Task[Any] | asyncio.Future[Any]:
        wrapped_coro = coro_wrapper(coro, coro_name=kwargs.get("name"))

        if original_factory is not None:
            t = original_factory(loop, wrapped_coro, **kwargs)
        else:
            t = asyncio.Task(wrapped_coro, loop=loop, **kwargs)

        _tasks_set.add(t)
        t.add_done_callback(_tasks_set.discard)
        return t

    loop.set_task_factory(new_factory)


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

    logging.getLogger("discord.app_commands.tree").addFilter(
        lambda record: "Ignoring exception in autocomplete for" not in record.getMessage()
    )
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)

    logger.add(log_dir, rotation="2 hours", retention="1 week", level="DEBUG")


def setup_sentry(sentry_dsn: str | None) -> None:
    if not CONFIG.sentry:
        logger.info("Sentry is disabled in the configuration.")
        return

    if sentry_dsn is None:
        logger.warning("Sentry DSN is not set, skipping Sentry initialization.")
        return

    sentry_sdk.init(
        dsn=sentry_dsn,
        disabled_integrations=[LoggingIntegration()],  # To avoid duplicate logs with loguru
        environment=CONFIG.env,
        release=get_project_version(),
        enable_logs=True,
    )


def setup_async_event_loop() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
