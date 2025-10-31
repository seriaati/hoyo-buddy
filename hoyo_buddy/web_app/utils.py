from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import ambr
import asyncpg
import flet as ft
import hakushin
import orjson
from cryptography.fernet import Fernet

from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import locale_to_starrail_data_lang, locale_to_zenless_data_lang
from hoyo_buddy.enums import Game
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient

from ..l10n import LocaleStr, translator

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hoyo_buddy.db.models import GachaHistory
    from hoyo_buddy.enums import Locale


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
                        width=16, height=16, stroke_width=2, color=ft.Colors.ON_SECONDARY_CONTAINER
                    ),
                    ft.Text(text, color=ft.Colors.ON_SECONDARY_CONTAINER),
                ]
            ),
            bgcolor=ft.Colors.SECONDARY_CONTAINER,
        )


class ErrorBanner(ft.Banner):
    def __init__(self, message: str, *, url: str | None = None) -> None:
        self.url = url
        actions: list[ft.Control] = [
            ft.IconButton(
                ft.Icons.CLOSE,
                on_click=self.on_action_click,
                icon_color=ft.Colors.ON_ERROR_CONTAINER,
            )
        ]
        if url:
            actions.insert(
                0,
                ft.IconButton(
                    ft.Icons.OPEN_IN_NEW,
                    on_click=self.launch_url,
                    icon_color=ft.Colors.ON_ERROR_CONTAINER,
                ),
            )

        super().__init__(
            leading=ft.Icon(ft.Icons.ERROR, color=ft.Colors.ON_ERROR_CONTAINER),
            content=ft.Text(message, color=ft.Colors.ON_ERROR_CONTAINER),
            bgcolor=ft.Colors.ERROR_CONTAINER,
            actions=actions,
        )

    async def launch_url(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        if self.url is None:
            return
        page.launch_url(self.url, web_window_name=ft.UrlTarget.BLANK.value)

    async def on_action_click(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        page.close(self)


def show_loading_snack_bar(
    page: ft.Page, *, message: str | None = None, locale: Locale | None = None
) -> ft.SnackBar:
    snack_bar = LoadingSnackBar(message=message, locale=locale)
    page.open(snack_bar)
    return snack_bar


def show_error_banner(page: ft.Page, *, message: str, url: str | None = None) -> None:
    page.open(ErrorBanner(message, url=url))


def decrypt_string(encrypted: str) -> str:
    key = Fernet(CONFIG.fernet_key)
    return key.decrypt(encrypted.encode()).decode()


def encrypt_string(string: str) -> str:
    key = Fernet(CONFIG.fernet_key)
    return key.encrypt(string.encode()).decode()


def clear_storage(
    page: ft.Page,
    *,
    user_id: int,
    cookies: bool = True,
    device_id: bool = False,
    device_fp: bool = False,
) -> None:
    if cookies:
        asyncio.create_task(page.client_storage.remove_async(f"hb.{user_id}.cookies"))
    if device_id:
        asyncio.create_task(page.client_storage.remove_async(f"hb.{user_id}.device_id"))
    if device_fp:
        asyncio.create_task(page.client_storage.remove_async(f"hb.{user_id}.device_fp"))


async def fetch_json_file(filename: str) -> Any:
    conn = await asyncpg.connect(CONFIG.db_url)
    try:
        json_string = await conn.fetchval('SELECT data FROM "jsonfile" WHERE name = $1', filename)
        return orjson.loads(json_string)
    finally:
        await conn.close()


async def fetch_gacha_names(
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
            async with hakushin.HakushinAPI(hakushin.Game.GI) as client:
                mw_costumes = await client.fetch_mw_costumes()
                mw_items = await client.fetch_mw_items()
                item_names.update({costume.id: costume.name for costume in mw_costumes})
                item_names.update({item.id: item.name for item in mw_items})
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


async def fetch_gacha_icons() -> dict[str, str]:
    gacha_icons: dict[str, str] = {}

    async with ambr.AmbrAPI() as api:
        weapons = await api.fetch_weapons()
        characters = await api.fetch_characters()

        gacha_icons.update({character.id: character.icon for character in characters})
        gacha_icons.update({str(weapon.id): weapon.icon for weapon in weapons})

    async with hakushin.HakushinAPI(hakushin.Game.GI) as client:
        mw_costumes = await client.fetch_mw_costumes()
        mw_items = await client.fetch_mw_items()

        # Costume takes precedence over item icon if both exist
        gacha_icons.update({str(item.id): item.icon for item in mw_items if item.icon is not None})
        gacha_icons.update({str(costume.id): costume.icon for costume in mw_costumes})

        for item in mw_items:
            if "Component Catalog" in item.name:
                costume_id = item.id - 10000
                gacha_icons[str(item.id)] = gacha_icons.get(str(costume_id), "")

    return gacha_icons


def get_gacha_icon(*, game: Game, item_id: int) -> str:
    """Get the icon URL for a gacha item."""
    if game is Game.ZZZ:
        return f"https://stardb.gg/api/static/zzz/{item_id}.png"

    if game is Game.GENSHIN:
        return f"https://stardb.gg/api/static/genshin/{item_id}.png"

    if game is Game.STARRAIL:
        if len(str(item_id)) == 5:  # light cone
            return f"https://stardb.gg/api/static/StarRailResWebp/icon/light_cone/{item_id}.webp"

        # character
        return f"https://stardb.gg/api/static/StarRailResWebp/icon/character/{item_id}.webp"

    msg = f"Unsupported game: {game}"
    raise ValueError(msg)


def refresh_page_view(page: ft.Page, view: ft.View, app_bar: ft.AppBar | None = None) -> None:
    view.scroll = ft.ScrollMode.AUTO
    if app_bar is not None:
        view.appbar = app_bar

    page.views.clear()
    page.views.append(view)
    page.update()
