from __future__ import annotations

import asyncio
import logging
import sys

import sentry_sdk
from loguru import logger
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.asyncpg import AsyncPGIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.loguru import LoggingLevels, LoguruIntegration

from hoyo_buddy.config import CONFIG
from hoyo_buddy.logging import InterceptHandler
from hoyo_buddy.utils.misc import get_project_version

__all__ = ("entry_point", "init_sentry")


def init_sentry() -> None:
    sentry_sdk.init(
        dsn=CONFIG.sentry_dsn,
        integrations=[
            AsyncioIntegration(),
            LoguruIntegration(
                level=LoggingLevels.INFO.value, event_level=LoggingLevels.ERROR.value
            ),
        ],
        disabled_integrations=[AsyncPGIntegration(), AioHttpIntegration(), LoggingIntegration()],
        traces_sample_rate=1.0,
        environment=CONFIG.env,
        enable_tracing=True,
        release=get_project_version(),
        _experiments={"enable_logs": True},
    )


def entry_point(log_dir: str) -> None:
    try:
        from icecream import install  # noqa: PLC0415
    except ImportError:
        pass
    else:
        install()

    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if CONFIG.is_dev else "INFO")
    if CONFIG.is_dev:
        logging.getLogger("tortoise").setLevel(logging.DEBUG)
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)
    logger.add(log_dir, rotation="2 hours", retention="1 week", level="DEBUG")

    logger.info(f"CLI args: {CONFIG.cli_args}")

    if CONFIG.sentry:
        init_sentry()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
