from __future__ import annotations

from typing import TYPE_CHECKING

from ..l10n import Translator
from .app import WebApp

if TYPE_CHECKING:
    import flet as ft


async def web_app_entry(page: ft.Page) -> None:
    async with Translator() as translator:
        app = WebApp(page, translator=translator)
    await app.initialize()
