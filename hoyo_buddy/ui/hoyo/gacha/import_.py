from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
import genshin

from hoyo_buddy.constants import MW_EVENT_BANNER_TYPES
from hoyo_buddy.db import GachaHistory, get_dyk, update_gacha_nums
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import COOKIE, LINK, LOADING
from hoyo_buddy.enums import Game, Platform
from hoyo_buddy.exceptions import AuthkeyExtractError, FeatureNotImplementedError, UIDMismatchError
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.hoyo.clients.gpy import GenshinClient
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button, Label, Modal, TextInput, URLButtonView, View

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from genshin.paginators import Paginator

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction, User

PS_CODE = """
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex "&{$((New-Object System.Net.WebClient).DownloadString('https://gacha.studiobutter.io.vn/start.ps1?ref_type=heads'))}"
"""
PS_CODE_URL = "https://github.com/studiobutter/gacha-stuff"
IOS_VIDEO_URL = "https://youtu.be/WfBpraUq41c"
ANDROID_VIDEO_URL = "https://youtu.be/CeQQoFKLwPY"


async def _fetch_new_records[RecordT: genshin.models.Unique](
    make_paginator: Callable[[int], Paginator[RecordT]],
    banner_types: Iterable[int],
    cursors: dict[str, int],
) -> list[RecordT]:
    """Fetch records newer than the per-banner cursors, updating `cursors` in place.

    Each banner's paginator yields records newest-first, so iteration stops (and no
    further API requests are made) once a record at or below the cursor is reached.
    """
    records: list[RecordT] = []

    for banner_type in banner_types:
        key = str(banner_type)
        cutoff = cursors.get(key, 0)

        async for record in make_paginator(banner_type):
            if record.id <= cutoff:
                break
            cursors[key] = max(cursors.get(key, 0), record.id)
            records.append(record)

    return records


def _zzz_signal_records(
    signals: list[genshin.models.SignalSearch], account: HoyoAccount
) -> list[GachaHistory]:
    return [
        GachaHistory(
            wish_id=signal.id,
            rarity=signal.rarity,
            time=signal.time,
            banner_type=signal.banner_type,
            item_id=signal.item_id,
            account=account,
            banner_id=None,
            game=Game.ZZZ,
        )
        for signal in signals
    ]


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
        if self.account.game is Game.ZZZ and self.account.platform is Platform.HOYOLAB:
            items.insert(0, HoyolabImport(self.account))
        self.add_items(items)
        await i.response.send_message(embed=self.embed, view=self, content=await get_dyk(i))
        self.message = await i.original_response()


class PCButton(Button[GachaImportView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="gacha_import_pc_player_button_label"),
            emoji="<:Desktop:1412046347179397150>",
            row=1,
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
        super().__init__(label="iOS", emoji="<:IOS:1412046328447635538>", row=1)

    async def callback(self, i: Interaction) -> Any:
        await i.response.send_message(content=IOS_VIDEO_URL, ephemeral=True)


class AndroidButton(Button[GachaImportView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="gacha_import_android_button_label"),
            emoji="<:Android:1412046338824339589>",
            row=1,
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

        client = GenshinClient(self.account)
        cursors = dict(self.account.gacha_cursors)
        signals = await _fetch_new_records(
            lambda b: client.chronicle_signal_history(b, uid=self.account.uid),
            genshin.models.ZZZBannerType,
            cursors,
        )
        signals.sort(key=lambda x: x.id)

        before = await GachaHistory.get_wish_count(self.account)
        await GachaHistory.bulk_create(_zzz_signal_records(signals, self.account))

        self.account.gacha_cursors = cursors
        await self.account.save(update_fields=("gacha_cursors",))

        after = await GachaHistory.get_wish_count(self.account)
        await update_gacha_nums(i.client.pool, account=self.account)

        await i.edit_original_response(embed=self.view.success_embed(after - before))


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

    def _check_uid(
        self,
        record: genshin.models.Wish
        | genshin.models.Warp
        | genshin.models.SignalSearch
        | genshin.models.MWWish,
    ) -> None:
        if record.uid != self.account.uid:
            raise UIDMismatchError(record.uid)

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

        await i.edit_original_response(embed=self.view.loading_embed, view=None)

        records: list[GachaHistory] = []
        cursors = dict(self.account.gacha_cursors)
        before = await GachaHistory.get_wish_count(self.account)

        if self.account.game is Game.GENSHIN:
            wishes = await _fetch_new_records(
                lambda b: client.wish_history(b, authkey=authkey),
                genshin.models.GenshinBannerType,
                cursors,
            )
            wishes.sort(key=lambda x: x.id)

            ambr = AmbrAPIClient(session=i.client.session)
            item_ids = await ambr.fetch_item_name_to_id_map()

            for wish in wishes:
                self._check_uid(wish)

                banner_type = 301 if wish.banner_type == 400 else wish.banner_type
                item_id = item_ids.get(wish.name)
                if item_id is None:
                    msg = f"Cannot find item ID for {wish.name}, is this an invalid item?"
                    raise ValueError(msg)

                records.append(
                    GachaHistory(
                        wish_id=wish.id,
                        rarity=wish.rarity,
                        time=wish.time,
                        banner_type=banner_type,
                        item_id=item_id,
                        account=self.account,
                        banner_id=None,
                        game=Game.GENSHIN,
                    )
                )

            mw_wishes = await _fetch_new_records(
                lambda b: client.mw_wish_history(b, authkey=authkey),
                (genshin.models.MWBannerType.STANDARD, genshin.models.MWBannerType.EVENT),
                cursors,
            )
            mw_wishes.sort(key=lambda x: x.id)

            for wish in mw_wishes:
                self._check_uid(wish)

                banner_type = (
                    2000 if wish.banner_type in MW_EVENT_BANNER_TYPES else wish.banner_type
                )

                records.append(
                    GachaHistory(
                        wish_id=wish.id,
                        rarity=wish.rarity,
                        time=wish.time,
                        banner_type=banner_type,
                        item_id=wish.item_id,
                        account=self.account,
                        banner_id=wish.banner_id,
                        game=Game.GENSHIN,
                    )
                )

        elif self.account.game is Game.STARRAIL:
            warps = await _fetch_new_records(
                lambda b: client.warp_history(b, authkey=authkey),
                genshin.models.StarRailBannerType,
                cursors,
            )
            warps.sort(key=lambda x: x.id)

            for warp in warps:
                self._check_uid(warp)

                records.append(
                    GachaHistory(
                        wish_id=warp.id,
                        rarity=warp.rarity,
                        time=warp.time,
                        banner_type=warp.banner_type,
                        item_id=warp.item_id,
                        account=self.account,
                        banner_id=warp.banner_id,
                        game=Game.STARRAIL,
                    )
                )

        elif self.account.game is Game.ZZZ:
            signals = await _fetch_new_records(
                lambda b: client.signal_history(b, authkey=authkey),
                genshin.models.ZZZBannerType,
                cursors,
            )
            signals.sort(key=lambda x: x.id)

            for signal in signals:
                self._check_uid(signal)

            records.extend(_zzz_signal_records(signals, self.account))
        else:
            raise FeatureNotImplementedError(platform=self.account.platform, game=self.account.game)

        await GachaHistory.bulk_create(records)

        self.account.gacha_cursors = cursors
        await self.account.save(update_fields=("gacha_cursors",))

        after = await GachaHistory.get_wish_count(self.account)
        await update_gacha_nums(i.client.pool, account=self.account)

        await i.edit_original_response(embed=self.view.success_embed(after - before))
