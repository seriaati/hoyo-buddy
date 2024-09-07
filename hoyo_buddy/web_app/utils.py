from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

import asyncpg
import flet as ft
import orjson
from cryptography.fernet import Fernet

from ..l10n import LocaleStr, Translator

if TYPE_CHECKING:
    from discord import Locale


class LoadingSnackBar(ft.SnackBar):
    def __init__(
        self,
        *,
        message: str | None = None,
        translator: Translator | None = None,
        locale: Locale | None = None,
    ) -> None:
        if translator is not None and locale is not None:
            text = translator.translate(LocaleStr(key="loading_text"), locale)
        else:
            text = message or "Loading..."

        super().__init__(
            content=ft.Row(
                [
                    ft.ProgressRing(
                        width=16, height=16, stroke_width=2, color=ft.colors.ON_SECONDARY_CONTAINER
                    ),
                    ft.Text(text, color=ft.colors.ON_SECONDARY_CONTAINER),
                ]
            ),
            bgcolor=ft.colors.SECONDARY_CONTAINER,
        )


class ErrorBanner(ft.Banner):
    def __init__(self, message: str) -> None:
        super().__init__(
            leading=ft.Icon(ft.icons.ERROR, color=ft.colors.ON_ERROR_CONTAINER),
            content=ft.Text(message, color=ft.colors.ON_ERROR_CONTAINER),
            bgcolor=ft.colors.ERROR_CONTAINER,
            actions=[
                ft.IconButton(
                    ft.icons.CLOSE,
                    on_click=self.on_action_click,
                    icon_color=ft.colors.ON_ERROR_CONTAINER,
                )
            ],
        )

    async def on_action_click(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        await page.close_banner_async()


async def show_loading_snack_bar(
    page: ft.Page,
    *,
    message: str | None = None,
    translator: Translator | None = None,
    locale: Locale | None = None,
) -> None:
    await page.show_snack_bar_async(
        LoadingSnackBar(message=message, translator=translator, locale=locale)
    )


async def show_error_banner(page: ft.Page, *, message: str) -> None:
    await page.show_banner_async(ErrorBanner(message))


def decrypt_string(encrypted: str) -> str:
    key = Fernet(os.environ["FERNET_KEY"])
    return key.decrypt(encrypted.encode()).decode()


def encrypt_string(string: str) -> str:
    key = Fernet(os.environ["FERNET_KEY"])
    return key.encrypt(string.encode()).decode()


def reset_storage(page: ft.Page, *, user_id: int) -> None:
    asyncio.create_task(page.client_storage.remove_async(f"hb.{user_id}.cookies"))
    asyncio.create_task(page.client_storage.remove_async(f"hb.{user_id}.device_id"))
    asyncio.create_task(page.client_storage.remove_async(f"hb.{user_id}.device_fp"))


async def fetch_json_file(filename: str) -> Any:
    conn = await asyncpg.connect(os.environ["DB_URL"])
    try:
        json_string = await conn.fetchval('SELECT data FROM "jsonfile" WHERE name = $1', filename)
        return orjson.loads(json_string)
    finally:
        await conn.close()
