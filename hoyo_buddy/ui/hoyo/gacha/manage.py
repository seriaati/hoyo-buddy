from __future__ import annotations

import datetime
import io
import time
from typing import TYPE_CHECKING, Any

import discord
import orjson
from discord import ButtonStyle

from hoyo_buddy.constants import UIGF_GAME_KEYS
from hoyo_buddy.db import GachaHistory, get_dyk
from hoyo_buddy.embeds import DefaultEmbed, ErrorEmbed
from hoyo_buddy.emojis import DELETE, EXPORT
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import UIGFHk4eRecord, UIGFHkrpgRecord, UIGFInfo, UIGFNapRecord, UIGFv4Record
from hoyo_buddy.ui import Button, View
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.enums import Locale
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
        view = self.view
        locale = view.locale
        account = view.account
        embed = ErrorEmbed(
            locale,
            title=LocaleStr(key="gacha_log_delete_confirm_embed_title"),
            description=LocaleStr(key="gacha_log_delete_confirm_embed_description"),
        )
        embed.add_acc_info(account)

        view.clear_items()
        view.add_item(DeleteConfirmButton())
        view.add_item(DeleteCancelButton())
        await i.response.edit_message(embed=embed, view=view)


class DeleteConfirmButton(Button[GachaLogManageView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="gacha_log_delete_confirm_button_label"),
            style=ButtonStyle.red,
            emoji=DELETE,
        )

    async def callback(self, i: Interaction) -> Any:
        await GachaHistory.filter(account=self.view.account).delete()
        self.view.account.gacha_cursors = {}
        await self.view.account.save(update_fields=("gacha_cursors",))
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

    def _to_uigf_record(self, wish: GachaHistory) -> UIGFv4Record:
        game = self.view.account.game
        fields: dict[str, Any] = {
            "id": wish.wish_id,
            "item_id": wish.item_id,
            "banner_type": wish.banner_type,
            "rarity": wish.rarity - 1 if game is Game.ZZZ else wish.rarity,
            "time": wish.time.astimezone(datetime.UTC),
        }
        if game is Game.GENSHIN:
            return UIGFHk4eRecord(gacha_type=wish.banner_type, **fields)
        gacha_id = str(wish.banner_id) if wish.banner_id is not None else None
        if game is Game.STARRAIL:
            return UIGFHkrpgRecord(gacha_id=gacha_id or "", **fields)
        return UIGFNapRecord(gacha_id=gacha_id, **fields)

    async def callback(self, i: Interaction) -> Any:
        await i.response.defer(ephemeral=ephemeral(i))

        info = UIGFInfo(
            export_timestamp=int(time.time()),
            export_app="Hoyo Buddy",
            export_app_version=i.client.version,
            version="v4.0",
        )
        game_info = {
            "uid": self.view.account.uid,
            "timezone": 0,
            "list": [
                self._to_uigf_record(wish).model_dump(by_alias=True, exclude_defaults=True)
                async for wish in GachaHistory.filter(account=self.view.account)
            ],
        }

        result: dict[str, Any] = {"info": info.model_dump()}
        result[UIGF_GAME_KEYS[self.view.account.game]] = [game_info]

        json_dump = orjson.dumps(result, option=orjson.OPT_INDENT_2)
        file_ = discord.File(
            filename=f"{self.view.account.uid}_hoyo_buddy_gacha_log_export_uigf_v4_0.json",
            fp=io.BytesIO(json_dump),
        )
        await i.followup.send(file=file_, ephemeral=True)
