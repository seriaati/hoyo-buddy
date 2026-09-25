from __future__ import annotations

import datetime
import io
import time
from typing import TYPE_CHECKING, Any

import discord
import orjson
from discord import ButtonStyle

from hoyo_buddy.constants import MW_BANNER_TYPES, UIGF_GAME_KEYS
from hoyo_buddy.db import GachaHistory, get_dyk
from hoyo_buddy.embeds import DefaultEmbed, ErrorEmbed
from hoyo_buddy.emojis import DELETE, EXPORT
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr
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

    async def callback(self, i: Interaction) -> Any:
        await i.response.defer(ephemeral=ephemeral(i))

        info = {
            "export_timestamp": int(time.time()),
            "export_app": "Hoyo Buddy",
            "export_app_version": i.client.version,
            "version": "v4.2",
        }

        is_genshin = self.view.account.game is Game.GENSHIN

        game_info = {
            "uid": self.view.account.uid,
            "timezone": 0,
            "list": [
                {
                    "id": str(x.wish_id),
                    "uigf_gacha_type": str(x.banner_type),
                    "gacha_type": str(x.banner_type),
                    "item_id": str(x.item_id),
                    "time": x.time.astimezone(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S"),
                    "rank_type": str(x.rarity - 1)
                    if self.view.account.game is Game.ZZZ
                    else str(x.rarity),
                }
                async for x in GachaHistory.filter(account=self.view.account)
                if not is_genshin or x.banner_type not in MW_BANNER_TYPES
            ],
        }

        if self.view.account.game is Game.STARRAIL:
            for item in game_info["list"]:
                item["gacha_id"] = ""

        result: dict[str, Any] = {"info": info}
        result[UIGF_GAME_KEYS[self.view.account.game]] = [game_info]

        if is_genshin:
            from hoyo_buddy.utils.gacha import fetch_mw_metadata
            from hoyo_buddy.constants import locale_to_hoyo_lang

            lang = locale_to_hoyo_lang(self.view.locale)
            mw_metadata = await fetch_mw_metadata(lang)

            hk4e_ugc = {
                "uid": self.view.account.uid,
                "timezone": 0,
                "lang": lang,
                "list": [
                    {
                        "id": str(x.wish_id),
                        "schedule_id": str(x.banner_id) if x.banner_id else "0",
                        "item_type": mw_metadata.get(str(x.item_id), {}).get(
                            "type", "BEYOND_MATERIAL_COSTUME"
                        ),
                        "item_id": str(x.item_id),
                        "item_name": mw_metadata.get(str(x.item_id), {}).get(
                            "name", "Unknown Item"
                        ),
                        "rank_type": str(x.rarity),
                        "time": x.time.astimezone(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S"),
                        "op_gacha_type": str(x.banner_type),
                    }
                    async for x in GachaHistory.filter(
                        account=self.view.account, banner_type__in=MW_BANNER_TYPES
                    )
                ],
            }
            if hk4e_ugc["list"]:
                result["hk4e_ugc"] = [hk4e_ugc]

        json_dump = orjson.dumps(result, option=orjson.OPT_INDENT_2)
        file_ = discord.File(
            filename=f"{self.view.account.uid}_hoyo_buddy_gacha_log_export_uigf_v4_2.json",
            fp=io.BytesIO(json_dump),
        )
        await i.followup.send(file=file_, ephemeral=True)
