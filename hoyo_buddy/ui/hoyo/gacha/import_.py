from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
import genshin

from hoyo_buddy.db.models import GachaHistory, HoyoAccount, get_dyk, get_last_gacha_num
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import LINK, LOADING
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import AuthkeyExtractError, FeatureNotImplementedError
from hoyo_buddy.hoyo.clients.gpy import GenshinClient
from hoyo_buddy.l10n import LocaleStr, Translator
from hoyo_buddy.ui.components import Button, Modal, TextInput, View
from hoyo_buddy.utils import ephemeral, item_name_to_id

if TYPE_CHECKING:
    from discord import Locale

    from hoyo_buddy.types import Interaction, User


class GachaImportView(View):
    def __init__(
        self, account: HoyoAccount, *, author: User, locale: Locale, translator: Translator
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.account = account

    @property
    def embed(self) -> DefaultEmbed:
        return DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(key="gacha_import_embed_title"),
            description=LocaleStr(key="gacha_import_embed_description"),
        ).add_acc_info(self.account)

    async def start(self, i: Interaction) -> Any:
        self.add_item(URLImport(self.account))
        await i.response.send_message(
            embed=self.embed, view=self, content=await get_dyk(i), ephemeral=ephemeral(i)
        )
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
        modal.translate(self.view.locale, self.view.translator)

        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
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
            self.view.translator,
            title=LocaleStr(key="gacha_import_loading_embed_title"),
            description=LocaleStr(
                key="gacha_import_loading_embed_description", loading_emoji=LOADING
            ),
        ).add_acc_info(self.account)
        await i.edit_original_response(embed=embed, view=None)

        count = 0

        if self.account.game is Game.GENSHIN:
            id_cache: dict[str, str] = {}

            banner_last_nums = {
                banner_type: await get_last_gacha_num(self.account, banner=banner_type)
                for banner_type in (100, 200, 301, 302, 500)
            }

            async for history in client.wish_history(authkey=authkey):
                if history.name not in id_cache:
                    item_id = id_cache[history.name] = await item_name_to_id(
                        i.client.session,
                        item_names=history.name,
                        game=Game.GENSHIN,
                        lang=client.lang,
                    )
                else:
                    item_id = id_cache[history.name]

                banner_type = 301 if history.banner_type == 400 else history.banner_type

                created = await GachaHistory.create(
                    wish_id=history.id,
                    rarity=history.rarity,
                    time=history.time,
                    banner_type=banner_type,
                    item_id=int(item_id),
                    account=self.account,
                    game=Game.GENSHIN,
                    num=banner_last_nums[banner_type] + 1,
                )
                if created:
                    count += 1
                    banner_last_nums[banner_type] += 1

        elif self.account.game is Game.STARRAIL:
            banner_last_nums = {
                banner_type: await get_last_gacha_num(self.account, banner=banner_type)
                for banner_type in (1, 2, 11, 12)
            }

            async for history in client.warp_history(authkey=authkey):
                created = await GachaHistory.create(
                    wish_id=history.id,
                    rarity=history.rarity,
                    time=history.time,
                    banner_type=history.banner_type,
                    item_id=history.item_id,
                    account=self.account,
                    game=Game.STARRAIL,
                    num=banner_last_nums[history.banner_type] + 1,
                )
                if created:
                    count += 1
                    banner_last_nums[history.banner_type] += 1

        elif self.account.game is Game.ZZZ:
            banner_last_nums = {
                banner_type: await get_last_gacha_num(self.account, banner=banner_type)
                for banner_type in (1, 2, 3, 5)
            }

            async for history in client.signal_history(authkey=authkey):
                created = await GachaHistory.create(
                    wish_id=history.id,
                    rarity=history.rarity,
                    time=history.time,
                    banner_type=history.banner_type,
                    item_id=history.item_id,
                    account=self.account,
                    game=Game.ZZZ,
                    num=banner_last_nums[history.banner_type] + 1,
                )
                if created:
                    count += 1
                    banner_last_nums[history.banner_type] += 1
        else:
            raise FeatureNotImplementedError(platform=self.account.platform, game=self.account.game)

        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(key="gacha_import_success_title"),
            description=LocaleStr(key="gacha_import_success_message", count=count),
        ).add_acc_info(self.account)
        await i.edit_original_response(embed=embed)
