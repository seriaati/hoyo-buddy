from __future__ import annotations

import io
import time
from typing import TYPE_CHECKING, Any

import discord
import orjson
from discord import ButtonStyle, Locale

from hoyo_buddy.constants import UIGF_GAME_KEYS
from hoyo_buddy.db import GachaHistory, HoyoAccount, get_dyk
from hoyo_buddy.embeds import DefaultEmbed, ErrorEmbed
from hoyo_buddy.emojis import DELETE, EXPORT
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button, View
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction, User


class GachaLogManageView(View):
    def __init__(self, account: HoyoAccount, *, author: User, locale: Locale) -> None:
        super().__init__(author=author, locale=locale)
        self.account = account

    async def start(self, i: Interaction) -> Any:
        log_count = await GachaHistory.filter(account=self.account).count()

        embed = DefaultEmbed(
            self.locale,
            title=LocaleStr(key="gacha_log_manage_embed_title"),
            description=LocaleStr(key="gacha_log_manage_embed_description", count=log_count),
        )
        embed.add_acc_info(self.account)

        self.add_item(ExportButton())
        self.add_item(DeleteButton())
        await i.response.send_message(embed=embed, view=self, content=await get_dyk(i))
        self.message = await i.original_response()


class DeleteButton(Button[GachaLogManageView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="gacha_log_delete_button_label"),
            style=ButtonStyle.red,
            emoji=DELETE,
        )

    async def callback(self, i: Interaction) -> Any:
        embed = ErrorEmbed(
            self.view.locale,
            title=LocaleStr(key="gacha_log_delete_confirm_embed_title"),
            description=LocaleStr(key="gacha_log_delete_confirm_embed_description"),
        )
        embed.add_acc_info(self.view.account)

        self.view.clear_items()
        self.view.add_item(DeleteConfirmButton())
        self.view.add_item(DeleteCancelButton())
        await i.response.edit_message(embed=embed, view=self.view)


class DeleteConfirmButton(Button[GachaLogManageView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="gacha_log_delete_confirm_button_label"),
            style=ButtonStyle.red,
            emoji=DELETE,
        )

    async def callback(self, i: Interaction) -> Any:
        await GachaHistory.filter(account=self.view.account).delete()
        embed = ErrorEmbed(
            self.view.locale,
            title=LocaleStr(key="gacha_log_delete_done_embed_title"),
            description=LocaleStr(key="gacha_log_delete_done_embed_description"),
        )
        embed.add_acc_info(self.view.account)
        await i.response.edit_message(embed=embed, view=None)


class DeleteCancelButton(Button[GachaLogManageView]):
    def __init__(self) -> None:
        super().__init__(label=LocaleStr(key="cancel_button_label"))

    async def callback(self, i: Interaction) -> Any:
        await i.response.edit_message(view=None)


class ExportButton(Button[GachaLogManageView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="gacha_log_export_button_label"),
            style=ButtonStyle.blurple,
            emoji=EXPORT,
        )

    async def callback(self, i: Interaction) -> Any:
        await i.response.defer(ephemeral=ephemeral(i))

        info = {
            "export_timestamp": int(time.time()),
            "export_app": "Hoyo Buddy",
            "export_app_version": i.client.version,
            "version": "v4.0",
        }
        game_info = {
            "uid": self.view.account.uid,
            "timezone": 8,
            "list": [
                {
                    "id": str(x.wish_id),
                    "uigf_gacha_type": str(x.banner_type),
                    "gacha_type": str(x.banner_type),
                    "item_id": str(x.item_id),
                    "time": x.time.astimezone().isoformat(),
                    "rank_type": str(x.rarity),
                }
                for x in await GachaHistory.filter(account=self.view.account).all()
            ],
        }
        if self.view.account.game is Game.STARRAIL:
            for item in game_info["list"]:
                item["gacha_id"] = ""

        result: dict[str, Any] = {"info": info}
        result[UIGF_GAME_KEYS[self.view.account.game]] = [game_info]

        json_dump = orjson.dumps(result, option=orjson.OPT_INDENT_2)
        file_ = discord.File(
            filename=f"{self.view.account.uid}_hoyo_buddy_gacha_log_export_uigf_v4_0.json",
            fp=io.BytesIO(json_dump),
        )
        await i.followup.send(file=file_, ephemeral=True)
