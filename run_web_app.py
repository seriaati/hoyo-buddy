from __future__ import annotations

import asyncio
import logging
import sys

import flet as ft
from dotenv import load_dotenv
from loguru import logger

from hoyo_buddy.l10n import Translator
from hoyo_buddy.logging import InterceptHandler
from hoyo_buddy.web_app.app import WebApp

translator = Translator()
loop = asyncio.get_event_loop()
loop.run_until_complete(translator.load())


async def web_app_entry(page: ft.Page) -> None:
    app = WebApp(page, translator=translator)
    await app.initialize()


if __name__ == "__main__":
    load_dotenv()

    logger.remove()
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)
    logger.add(sys.stderr, level="INFO")
    ft.app(web_app_entry, port=8645, view=None, assets_dir="hoyo_buddy/web_app/assets")

    loop.run_until_complete(translator.unload())
    loop.close()
