from __future__ import annotations

import asyncio

import flet as ft

from hoyo_buddy.l10n import translator
from hoyo_buddy.utils import entry_point
from hoyo_buddy.web_app.app import ClientStorage, WebApp


async def web_app_entry(page: ft.Page) -> None:
    setattr(page, f"_{page.__class__.__name__}__client_storage", ClientStorage(page))
    app = WebApp(page)
    await app.initialize()


if __name__ == "__main__":
    entry_point("logs/web_app.log")
    asyncio.run(translator.load())
    ft.app(
        web_app_entry,
        port=8645,
        view=None,
        assets_dir="hoyo_buddy/web_app/assets",
        use_color_emoji=True,
    )
