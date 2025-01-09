from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

import ambr
import asyncpg
import flet as ft
import orjson
from cryptography.fernet import Fernet

from hoyo_buddy.constants import locale_to_starrail_data_lang, locale_to_zenless_data_lang
from hoyo_buddy.enums import Game
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient

from ..l10n import LocaleStr, translator

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import Locale

    from hoyo_buddy.db.models import GachaHistory


class LoadingSnackBar(ft.SnackBar):
    def __init__(self, *, message: str | None = None, locale: Locale | None = None) -> None:
        if locale is not None:
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
    def __init__(self, message: str, *, url: str | None = None) -> None:
        self.url = url
        actions: list[ft.Control] = [
            ft.IconButton(
                ft.icons.CLOSE,
                on_click=self.on_action_click,
                icon_color=ft.colors.ON_ERROR_CONTAINER,
            )
        ]
        if url:
            actions.insert(
                0,
                ft.IconButton(
                    ft.icons.OPEN_IN_NEW,
                    on_click=self.launch_url,
                    icon_color=ft.colors.ON_ERROR_CONTAINER,
                ),
            )

        super().__init__(
            leading=ft.Icon(ft.icons.ERROR, color=ft.colors.ON_ERROR_CONTAINER),
            content=ft.Text(message, color=ft.colors.ON_ERROR_CONTAINER),
            bgcolor=ft.colors.ERROR_CONTAINER,
            actions=actions,
        )

    async def launch_url(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        if self.url is None:
            return
        await page.launch_url_async(self.url, web_window_name=ft.UrlTarget.BLANK.value)

    async def on_action_click(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        await page.close_banner_async()


async def show_loading_snack_bar(
    page: ft.Page, *, message: str | None = None, locale: Locale | None = None
) -> None:
    await page.show_snack_bar_async(LoadingSnackBar(message=message, locale=locale))


async def show_error_banner(page: ft.Page, *, message: str, url: str | None = None) -> None:
    await page.show_banner_async(ErrorBanner(message, url=url))


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


async def get_gacha_names(
    page: ft.Page, *, gachas: Sequence[GachaHistory], locale: Locale, game: Game
) -> dict[int, str]:
    cached_gacha_names: dict[str, str] = (
        await page.client_storage.get_async(f"hb.{locale}.{game.name}.gacha_names") or {}
    )

    result: dict[int, str] = {}
    item_ids = list({g.item_id for g in gachas})
    non_cached_item_ids: list[int] = []

    for item_id in item_ids:
        if str(item_id) in cached_gacha_names:
            result[item_id] = cached_gacha_names[str(item_id)]
        else:
            non_cached_item_ids.append(item_id)

    if non_cached_item_ids:
        # Update the cache with the new item names
        if game is Game.ZZZ:
            map_: dict[str, str] = await fetch_json_file(
                f"zzz_item_names_{locale_to_zenless_data_lang(locale)}.json"
            )
            item_names = {int(k): v for k, v in map_.items()}
        elif game is Game.STARRAIL:
            map_: dict[str, str] = await fetch_json_file(
                f"hsr_item_names_{locale_to_starrail_data_lang(locale)}.json"
            )
            item_names = {int(k): v for k, v in map_.items()}
        elif game is Game.GENSHIN:
            async with AmbrAPIClient(locale) as client:
                item_names = await client.fetch_item_id_to_name_map()
        else:
            msg = f"Unsupported game: {game} for fetching gacha names"
            raise ValueError(msg)

        for item_id in non_cached_item_ids:
            result[item_id] = item_names.get(item_id, "???")

        cached_gacha_names.update({str(k): v for k, v in item_names.items()})
        asyncio.create_task(
            page.client_storage.set_async(
                f"hb.{locale}.{game.name}.gacha_names", cached_gacha_names
            )
        )

    return result


async def get_gacha_icon(*, game: Game, item_id: int) -> str:
    """Get the icon URL for a gacha item."""
    if game is Game.ZZZ:
        return f"https://stardb.gg/api/static/zzz/{item_id}.png"

    if game is Game.GENSHIN:
        async with ambr.AmbrAPI() as api:
            if len(str(item_id)) == 5:  # weapon
                weapon = await api.fetch_weapon_detail(item_id)
                return weapon.icon

            character = await api.fetch_character_detail(str(item_id))
            return character.icon

    if game is Game.STARRAIL:
        if len(str(item_id)) == 5:  # light cone
            return f"https://stardb.gg/api/static/StarRailResWebp/icon/light_cone/{item_id}.webp"

        # character
        return f"https://stardb.gg/api/static/StarRailResWebp/icon/character/{item_id}.webp"

    msg = f"Unsupported game: {game}"
    raise ValueError(msg)
