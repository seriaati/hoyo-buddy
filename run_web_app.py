from __future__ import annotations

import asyncio
import logging
import sys

import flet as ft
from loguru import logger

from hoyo_buddy.config import CONFIG
from hoyo_buddy.l10n import translator
from hoyo_buddy.logging import InterceptHandler
from hoyo_buddy.utils import init_sentry
from hoyo_buddy.web_app.app import WebApp

env = CONFIG.env
is_dev = env == "dev"

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def web_app_entry(page: ft.Page) -> None:
    app = WebApp(page)
    await app.initialize()


if __name__ == "__main__":
    logger.remove()
    if CONFIG.sentry:
        init_sentry()

    logger.add(sys.stderr, level="DEBUG" if is_dev else "INFO")
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)
    logger.add("logs/web_app.log", rotation="1 day", retention="2 weeks", level="DEBUG")

    asyncio.run(translator.load())

    ft.app(
        web_app_entry,
        port=8645,
        view=None,
        assets_dir="hoyo_buddy/web_app/assets",
        use_color_emoji=True,
    )
