from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
import genshin

from hoyo_buddy.db import GachaHistory, HoyoAccount, get_dyk, update_gacha_nums
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import LINK, LOADING
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import AuthkeyExtractError, FeatureNotImplementedError
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.hoyo.clients.gpy import GenshinClient
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.components import Button, Modal, TextInput, View

if TYPE_CHECKING:
    from discord import Locale

    from hoyo_buddy.types import Interaction, User


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

    async def start(self, i: Interaction) -> Any:
        self.add_item(URLImport(self.account))
        await i.response.send_message(embed=self.embed, view=self, content=await get_dyk(i))
        self.message = await i.original_response()


class EnterURLModal(Modal):
    url = TextInput(label="URL", style=discord.TextStyle.long)

    def __init__(self) -> None:
        super().__init__(title=LocaleStr(key="gacha_import_url_modal_title"))


class URLImport(Button[GachaImportView]):
    def __init__(self, account: HoyoAccount) -> None:
        super().__init__(
            label=LocaleStr(key="gacha_import_url_modal_title"),
            emoji=LINK,
            style=discord.ButtonStyle.primary,
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
        client = GenshinClient(self.account)
        try:
            authkey = genshin.utility.extract_authkey(url)
        except Exception as e:
            raise AuthkeyExtractError from e

        if authkey is None:
            raise AuthkeyExtractError

        embed = DefaultEmbed(
            self.view.locale,
            title=LocaleStr(key="gacha_import_loading_embed_title"),
            description=LocaleStr(
                key="gacha_import_loading_embed_description", loading_emoji=LOADING
            ),
        ).add_acc_info(self.account)
        await i.edit_original_response(embed=embed, view=None)

        count = 0

        if self.account.game is Game.GENSHIN:
            wishes: list[genshin.models.Wish] = [
                history async for history in client.wish_history(authkey=authkey)
            ]
            wishes.sort(key=lambda x: x.id)

            client = AmbrAPIClient(session=i.client.session)
            item_ids = await client.fetch_item_name_to_id_map()

            for wish in wishes:
                banner_type = 301 if wish.banner_type == 400 else wish.banner_type
                item_id = item_ids.get(wish.name)
                if item_id is None:
                    msg = f"Cannot find item ID for {wish.name}, is this an invalid item?"
                    raise ValueError(msg)

                created = await GachaHistory.create(
                    wish_id=wish.id,
                    rarity=wish.rarity,
                    time=wish.time,
                    banner_type=banner_type,
                    item_id=item_id,
                    account=self.account,
                )
                if created:
                    count += 1

        elif self.account.game is Game.STARRAIL:
            warps: list[genshin.models.Warp] = [
                history async for history in client.warp_history(authkey=authkey)
            ]
            warps.sort(key=lambda x: x.id)

            for warp in warps:
                created = await GachaHistory.create(
                    wish_id=warp.id,
                    rarity=warp.rarity,
                    time=warp.time,
                    banner_type=warp.banner_type,
                    item_id=warp.item_id,
                    account=self.account,
                )
                if created:
                    count += 1

        elif self.account.game is Game.ZZZ:
            signals: list[genshin.models.SignalSearch] = [
                history async for history in client.signal_history(authkey=authkey)
            ]
            signals.sort(key=lambda x: x.id)

            for signal in signals:
                created = await GachaHistory.create(
                    wish_id=signal.id,
                    rarity=signal.rarity + 1,
                    time=signal.time,
                    banner_type=signal.banner_type,
                    item_id=signal.item_id,
                    account=self.account,
                )
                if created:
                    count += 1
        else:
            raise FeatureNotImplementedError(platform=self.account.platform, game=self.account.game)

        await update_gacha_nums(i.client.pool, account=self.account)

        embed = DefaultEmbed(
            self.view.locale,
            title=LocaleStr(key="gacha_import_success_title"),
            description=LocaleStr(key="gacha_import_success_message", count=count),
        ).add_acc_info(self.account)
        await i.edit_original_response(embed=embed)
