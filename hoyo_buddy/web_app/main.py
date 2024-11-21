from __future__ import annotations

from typing import TYPE_CHECKING

from .app import WebApp

if TYPE_CHECKING:
    import flet as ft


async def web_app_entry(page: ft.Page) -> None:
    app = WebApp(page)
    await app.initialize()
