from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
import genshin

from hoyo_buddy.db import get_dyk
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import ANDROID, COOKIE, DESKTOP, IOS, LINK, LOADING
from hoyo_buddy.enums import Game, Platform
from hoyo_buddy.exceptions import AuthkeyExtractError, FeatureNotImplementedError
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.hoyo.clients.gpy import GenshinClient
from hoyo_buddy.hoyo.gacha_import import (
    fetch_authkey,
    fetch_genshin_records,
    fetch_starrail_records,
    fetch_zzz_chronicle_records,
    fetch_zzz_records,
    save_records,
)
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button, Label, Modal, TextInput, URLButtonView, View

if TYPE_CHECKING:
    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction, User

PS_CODE = """
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex "&{$((New-Object System.Net.WebClient).DownloadString('https://gacha.studiobutter.io.vn/start.ps1?ref_type=heads'))}"
"""
PS_CODE_URL = "https://github.com/studiobutter/gacha-stuff"
IOS_VIDEO_URL = "https://youtu.be/WfBpraUq41c"
ANDROID_VIDEO_URL = "https://youtu.be/CeQQoFKLwPY"


class GachaImportView(View):
    def __init__(self, account: HoyoAccount, *, author: User, locale: Locale) -> None:
        super().__init__(author=author, locale=locale)
        self.account = account

    @property
    def embed(self) -> DefaultEmbed:
        return DefaultEmbed(
            self.locale,
            title=LocaleStr(key="gacha_import_loading_embed_title"),
            description=LocaleStr(key="gacha_import_embed_description"),
        ).add_acc_info(self.account)

    @property
    def loading_embed(self) -> DefaultEmbed:
        return DefaultEmbed(
            self.locale,
            title=LocaleStr(key="gacha_import_loading_embed_title"),
            description=LocaleStr(
                key="gacha_import_loading_embed_description", loading_emoji=LOADING
            ),
        ).add_acc_info(self.account)

    def success_embed(self, count: int) -> DefaultEmbed:
        return DefaultEmbed(
            self.locale,
            title=LocaleStr(key="gacha_import_success_title"),
            description=LocaleStr(key="gacha_import_success_message", count=count),
        ).add_acc_info(self.account)

    async def start(self, i: Interaction) -> Any:
        items: list[Button[GachaImportView]] = [
            URLImport(self.account),
            PCButton(),
            IOSButton(),
            AndroidButton(),
        ]
        if self.account.platform is Platform.HOYOLAB and (
            self.account.game is Game.ZZZ
            or (self.account.game is Game.GENSHIN and self.account.can_use_cookie_token)
        ):
            items.insert(0, HoyolabImport(self.account))
        self.add_items(items)
        await i.response.send_message(embed=self.embed, view=self, content=await get_dyk(i))
        self.message = await i.original_response()

    async def import_with_authkey(self, i: Interaction, authkey: str) -> None:
        client = GenshinClient(self.account)
        cursors = dict(self.account.gacha_cursors)

        if self.account.game is Game.GENSHIN:
            ambr = AmbrAPIClient(session=i.client.session)
            records = await fetch_genshin_records(
                client,
                self.account,
                authkey=authkey,
                cursors=cursors,
                item_ids=await ambr.fetch_item_name_to_id_map(),
            )
        elif self.account.game is Game.STARRAIL:
            records = await fetch_starrail_records(
                client, self.account, authkey=authkey, cursors=cursors
            )
        elif self.account.game is Game.ZZZ:
            records = await fetch_zzz_records(
                client, self.account, authkey=authkey, cursors=cursors
            )
        else:
            raise FeatureNotImplementedError(platform=self.account.platform, game=self.account.game)

        count = await save_records(self.account, records, cursors=cursors, pool=i.client.pool)
        await i.edit_original_response(embed=self.success_embed(count))


class PCButton(Button[GachaImportView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="gacha_import_pc_player_button_label"), emoji=DESKTOP, row=1
        )

    async def callback(self, i: Interaction) -> Any:
        embed = DefaultEmbed(
            self.view.locale,
            title=self.label,
            description=LocaleStr(key="gacha_import_pc_import_embed_desc"),
        )
        view = URLButtonView(
            self.view.locale, url=PS_CODE_URL, label=LocaleStr(key="gacha_import_pc_source_code")
        )
        await i.response.send_message(embed=embed, ephemeral=True, view=view)
        await i.followup.send(content=PS_CODE, ephemeral=True, suppress_embeds=True)


class IOSButton(Button[GachaImportView]):
    def __init__(self) -> None:
        super().__init__(label="iOS", emoji=IOS, row=1)

    async def callback(self, i: Interaction) -> Any:
        await i.response.send_message(content=IOS_VIDEO_URL, ephemeral=True)


class AndroidButton(Button[GachaImportView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="gacha_import_android_button_label"), emoji=ANDROID, row=1
        )

    async def callback(self, i: Interaction) -> Any:
        await i.response.send_message(content=ANDROID_VIDEO_URL, ephemeral=True)


class HoyolabImport(Button[GachaImportView]):
    def __init__(self, account: HoyoAccount) -> None:
        super().__init__(
            label=LocaleStr(key="gacha_import_hoyolab_button_label"),
            emoji=COOKIE,
            style=discord.ButtonStyle.primary,
            row=0,
        )
        self.account = account

    async def callback(self, i: Interaction) -> Any:
        await i.response.defer()
        await i.edit_original_response(embed=self.view.loading_embed, view=None)

        if self.account.game is Game.ZZZ:
            await self._import_from_chronicle(i)
        else:
            await self.view.import_with_authkey(i, await self._fetch_authkey())

    async def _fetch_authkey(self) -> str:
        return await fetch_authkey(GenshinClient(self.account), self.account)

    async def _import_from_chronicle(self, i: Interaction) -> None:
        cursors = dict(self.account.gacha_cursors)
        records = await fetch_zzz_chronicle_records(
            GenshinClient(self.account), self.account, cursors=cursors
        )
        count = await save_records(self.account, records, cursors=cursors, pool=i.client.pool)
        await i.edit_original_response(embed=self.view.success_embed(count))


class EnterURLModal(Modal):
    url: Label[TextInput] = Label(text="URL", component=TextInput(style=discord.TextStyle.long))

    def __init__(self) -> None:
        super().__init__(title=LocaleStr(key="gacha_import_url_modal_title"))


class URLImport(Button[GachaImportView]):
    def __init__(self, account: HoyoAccount) -> None:
        super().__init__(
            label=LocaleStr(key="gacha_import_url_modal_title"),
            emoji=LINK,
            style=discord.ButtonStyle.primary,
            row=0,
        )
        self.account = account

    async def callback(self, i: Interaction) -> Any:
        modal = EnterURLModal()
        modal.translate(self.view.locale)

        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        url = modal.url.value
        try:
            authkey = genshin.utility.extract_authkey(url)
        except Exception as e:
            raise AuthkeyExtractError from e

        if authkey is None:
            raise AuthkeyExtractError

        await i.edit_original_response(embed=self.view.loading_embed, view=None)
        await self.view.import_with_authkey(i, authkey)
