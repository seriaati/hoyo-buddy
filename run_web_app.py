from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

import flet as ft
from dotenv import load_dotenv
from loguru import logger

from hoyo_buddy.l10n import translator
from hoyo_buddy.logging import InterceptHandler
from hoyo_buddy.utils import init_sentry
from hoyo_buddy.web_app.app import WebApp

load_dotenv()
env = os.environ["ENV"]  # dev, prod, test
is_dev = env == "dev"

parser = argparse.ArgumentParser()
parser.add_argument("--sentry", action="store_true", default=not is_dev)
args = parser.parse_args()

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def web_app_entry(page: ft.Page) -> None:
    app = WebApp(page)
    await app.initialize()


if __name__ == "__main__":
    load_dotenv()

    logger.remove()
    if args.sentry:
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
