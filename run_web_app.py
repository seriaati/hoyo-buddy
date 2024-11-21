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

loop = asyncio.get_event_loop()
loop.run_until_complete(translator.load())


async def web_app_entry(page: ft.Page) -> None:
    app = WebApp(page)
    await app.initialize()


if __name__ == "__main__":
    load_dotenv()

    logger.remove()
    if args.sentry:
        init_sentry()

    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)
    logger.add(sys.stderr, level="INFO")
    ft.app(web_app_entry, port=8645, view=None, assets_dir="hoyo_buddy/web_app/assets", use_color_emoji=True)

    loop.run_until_complete(translator.unload())
    loop.close()
