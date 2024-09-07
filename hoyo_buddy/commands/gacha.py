from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

import ambr
import hakushin
import orjson
import pandas as pd
import yatta

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import UIGF_GAME_KEYS
from hoyo_buddy.db.models import GachaHistory, HoyoAccount, get_last_gacha_num, get_locale
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import LOADING
from hoyo_buddy.enums import GachaImportSource, Game
from hoyo_buddy.exceptions import FeatureNotImplementedError, InvalidFileExtError, UIDMismatchError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import (
    SRGFRecord,
    StarDBRecord,
    StarRailStationRecord,
    UIGFRecord,
    ZZZRngMoeRecord,
)
from hoyo_buddy.ui.hoyo.gacha.import_ import GachaImportView
from hoyo_buddy.ui.hoyo.gacha.manage import GachaLogManageView
from hoyo_buddy.ui.hoyo.gacha.view import ViewGachaLogView

if TYPE_CHECKING:
    import discord

    from hoyo_buddy.types import Interaction


class GachaCommand:
    @staticmethod
    def _validate_file_extension(file: discord.Attachment, accept_ext: str) -> None:
        extension = file.filename.split(".")[-1]
        if extension != accept_ext:
            raise InvalidFileExtError(accept_ext)

    async def _srs_import(
        self, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """Star Rail Station import."""
        self._validate_file_extension(file, "csv")

        bytes_ = await file.read()
        records_df = await i.client.loop.run_in_executor(
            i.client.executor, pd.read_csv, io.BytesIO(bytes_)
        )
        data: list[dict[str, Any]] = records_df.to_dict(orient="records")  # pyright: ignore[reportAssignmentType]
        records = [StarRailStationRecord(**record) for record in data]

        record_banners = {record.banner_type for record in records}
        banner_last_nums = {
            banner_type: await get_last_gacha_num(account, banner=banner_type)
            for banner_type in record_banners
        }

        count = 0

        for record in records:
            created = await GachaHistory.create(
                wish_id=record.id,
                rarity=record.rarity,
                item_id=record.item_id,
                banner_type=record.banner_type,
                account=account,
                num=banner_last_nums[record.banner_type] + 1,
                time=record.time,
            )
            if created:
                count += 1
                banner_last_nums[record.banner_type] += 1

        return count

    async def _zzz_rng_moe_import(
        self, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """zzz.rng.moe import."""
        self._validate_file_extension(file, "json")

        bytes_ = await file.read()
        data = await i.client.loop.run_in_executor(i.client.executor, orjson.loads, bytes_)
        uid = str(data["data"]["profiles"]["1"]["bindUid"])
        if uid != str(account.uid):
            raise UIDMismatchError(uid)

        if len(uid) != 8 and uid.startswith("10"):  # us
            tz_hour = -5
        elif len(uid) != 8 and uid.startswith("15"):  # eu
            tz_hour = 1
        else:
            tz_hour = 8

        gacha_types = ("1001", "2001", "3001", "5001")
        records: list[ZZZRngMoeRecord] = []
        for gacha_type in gacha_types:
            records.extend(
                [
                    ZZZRngMoeRecord(tz_hour=tz_hour, **record)
                    for record in data["data"]["profiles"]["1"]["stores"]["0"]["items"][gacha_type]
                ]
            )

        record_banners = {record.banner_type for record in records}
        banner_last_nums = {
            banner_type: await get_last_gacha_num(account, banner=banner_type)
            for banner_type in record_banners
        }

        count = 0

        for record in records:
            created = await GachaHistory.create(
                wish_id=record.id,
                rarity=record.rarity,
                item_id=record.item_id,
                banner_type=record.banner_type,
                account=account,
                num=banner_last_nums[record.banner_type] + 1,
                time=record.time,
            )
            if created:
                count += 1
                banner_last_nums[record.banner_type] += 1

        return count

    async def _stardb_import(
        self, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """stardb import."""
        self._validate_file_extension(file, "json")

        bytes_ = await file.read()
        data = await i.client.loop.run_in_executor(i.client.executor, orjson.loads, bytes_)

        if account.game is Game.STARRAIL:
            return await self._stardb_hsr_import(account, data)
        if account.game is Game.GENSHIN:
            return await self._stardb_gi_import(account, data)
        if account.game is Game.ZZZ:
            return await self._stardb_zzz_import(account, data)

        raise FeatureNotImplementedError(game=account.game)

    async def _stardb_hsr_import(self, account: HoyoAccount, data: dict[str, Any]) -> int:
        hsr_data = next(
            (d["warps"] for d in data["user"]["hsr"]["uids"] if d["uid"] == account.uid), None
        )
        if hsr_data is not None:
            banner_types: dict[str, int] = {
                "departure": 2,
                "standard": 1,
                "character": 11,
                "light_cone": 12,
            }
            records: list[StarDBRecord] = []
            for banner_name, banner_type in banner_types.items():
                records.extend(
                    [
                        StarDBRecord(banner_type=banner_type, **record)
                        for record in hsr_data[banner_name]
                    ]
                )

            if records:
                # Fetch rarity map with Yatta API
                async with yatta.YattaAPI() as api:
                    characters = await api.fetch_characters()
                    lcs = await api.fetch_light_cones()

                rarity_map: dict[int, int] = {
                    character.id: character.rarity for character in characters
                } | {lc.id: lc.rarity for lc in lcs}

                record_banners = {record.banner_type for record in records}
                banner_last_nums = {
                    banner_type: await get_last_gacha_num(account, banner=banner_type)
                    for banner_type in record_banners
                }

                count = 0

                for record in records:
                    created = await GachaHistory.create(
                        wish_id=record.id,
                        rarity=rarity_map[record.item_id],
                        item_id=record.item_id,
                        banner_type=record.banner_type,
                        account=account,
                        num=banner_last_nums[record.banner_type] + 1,
                        time=record.time,
                    )
                    if created:
                        count += 1
                        banner_last_nums[record.banner_type] += 1

                return count

        return 0

    async def _stardb_gi_import(self, account: HoyoAccount, data: dict[str, Any]) -> int:
        gi_data = next(
            (d["wishes"] for d in data["user"]["gi"]["uids"] if d["uid"] == account.uid), None
        )
        if gi_data is not None:
            banner_types: dict[str, int] = {
                "beginner": 100,
                "standard": 200,
                "character": 301,
                "weapon": 302,
                "chronicled": 500,
            }

            records: list[StarDBRecord] = []
            for banner_name, banner_type in banner_types.items():
                records.extend(
                    [
                        StarDBRecord(banner_type=banner_type, **record)
                        for record in gi_data[banner_name]
                    ]
                )

            if records:
                # Fetch rarity map with Ambr API
                async with ambr.AmbrAPI() as api:
                    characters = await api.fetch_characters()
                    weapons = await api.fetch_weapons()

                items = characters + weapons
                rarity_map: dict[int, int] = {}
                for item in items:
                    if isinstance(item.id, str) and not item.id.isdigit():
                        continue
                    rarity_map[int(item.id)] = item.rarity

                banner_last_nums = {
                    banner_type: await get_last_gacha_num(account, banner=banner_type)
                    for banner_type in banner_types.values()
                }

                count = 0

                for record in records:
                    created = await GachaHistory.create(
                        wish_id=record.id,
                        rarity=rarity_map[record.item_id],
                        item_id=record.item_id,
                        banner_type=record.banner_type,
                        account=account,
                        time=record.time,
                        num=banner_last_nums[record.banner_type] + 1,
                    )
                    if created:
                        count += 1
                        banner_last_nums[record.banner_type] += 1

                return count

        return 0

    async def _stardb_zzz_import(self, account: HoyoAccount, data: dict[str, Any]) -> int:
        zzz_data = next(
            (d["signals"] for d in data["user"]["zzz"]["uids"] if d["uid"] == account.uid), None
        )
        if zzz_data is not None:
            banner_types: dict[str, int] = {
                "standard": 1,
                "character": 2,
                "w_engine": 3,
                "bangboo": 5,
            }
            records: list[StarDBRecord] = []
            for banner_name, banner_type in banner_types.items():
                records.extend(
                    [
                        StarDBRecord(banner_type=banner_type, **record)
                        for record in zzz_data[banner_name]
                    ]
                )

            if records:
                # Fetch rarity map with Hakushin API
                async with hakushin.HakushinAPI(hakushin.Game.ZZZ) as api:
                    characters = await api.fetch_characters()
                    bangboos = await api.fetch_bangboos()
                    w_engines = await api.fetch_weapons()

                items = characters + bangboos + w_engines
                rarity_map: dict[int, int] = {}
                rarity_converter: dict[str, int] = {"S": 5, "A": 4, "B": 3}
                for item in items:
                    if item.rarity is None:
                        continue
                    rarity_map[item.id] = rarity_converter[item.rarity]

                record_banners = {record.banner_type for record in records}
                banner_last_nums = {
                    banner_type: await get_last_gacha_num(account, banner=banner_type)
                    for banner_type in record_banners
                }

                count = 0

                for record in records:
                    created = await GachaHistory.create(
                        wish_id=record.id,
                        rarity=rarity_map[record.item_id],
                        item_id=record.item_id,
                        banner_type=record.banner_type,
                        account=account,
                        num=banner_last_nums[record.banner_type] + 1,
                        time=record.time,
                    )
                    if created:
                        count += 1
                        banner_last_nums[record.banner_type] += 1

                return count

        return 0

    async def _uigf_import(
        self, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """UIGF import."""
        self._validate_file_extension(file, "json")

        bytes_ = await file.read()
        data = await i.client.loop.run_in_executor(i.client.executor, orjson.loads, bytes_)

        # Determine UIGF v4.0
        is_v4 = data["info"].get("version") == "v4.0"

        if is_v4:
            game_data = next(
                (d for d in data[UIGF_GAME_KEYS[account.game]] if int(d["uid"]) == account.uid),
                None,
            )
            if game_data is None:
                raise UIDMismatchError(account.uid)

            tz_hour = game_data["timezone"]
            records = [UIGFRecord(timezone=tz_hour, **record) for record in game_data["list"]]
        else:
            uid = str(data["info"]["uid"])
            if uid != str(account.uid):
                raise UIDMismatchError(uid)

            # Timezone handling
            tz_hour = data["info"].get("region_time_zone")
            if tz_hour is None:
                if uid.startswith("6"):  # us
                    tz_hour = -5
                elif uid.startswith("7"):  # eu
                    tz_hour = 1
                else:
                    tz_hour = 8

            records = [UIGFRecord(timezone=tz_hour, **record) for record in data["list"]]

        record_banners = {record.banner_type for record in records}
        banner_last_nums = {
            banner_type: await get_last_gacha_num(account, banner=banner_type)
            for banner_type in record_banners
        }

        count = 0

        for record in records:
            created = await GachaHistory.create(
                wish_id=record.id,
                rarity=record.rarity,
                item_id=record.item_id,
                banner_type=record.banner_type,
                account=account,
                num=banner_last_nums[record.banner_type] + 1,
                time=record.time,
            )
            if created:
                count += 1
                banner_last_nums[record.banner_type] += 1

        return count

    async def _srgf_import(
        self, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """SRGF import."""
        self._validate_file_extension(file, "json")

        bytes_ = await file.read()
        data = await i.client.loop.run_in_executor(i.client.executor, orjson.loads, bytes_)

        uid = str(data["info"]["uid"])
        if uid != str(account.uid):
            raise UIDMismatchError(uid)

        tz_hour = data["info"]["region_time_zone"]
        records = [SRGFRecord(timezone=tz_hour, **record) for record in data["list"]]

        record_banners = {record.banner_type for record in records}
        banner_last_nums = {
            banner_type: await get_last_gacha_num(account, banner=banner_type)
            for banner_type in record_banners
        }

        count = 0

        for record in records:
            created = await GachaHistory.create(
                wish_id=record.id,
                rarity=record.rarity,
                item_id=record.item_id,
                banner_type=record.banner_type,
                account=account,
                num=banner_last_nums[record.banner_type] + 1,
                time=record.time,
            )
            if created:
                count += 1
                banner_last_nums[record.banner_type] += 1

        return count

    async def run_import(self, i: Interaction, account: HoyoAccount) -> None:
        locale = await get_locale(i)
        view = GachaImportView(
            account, author=i.user, locale=locale, translator=i.client.translator
        )
        await view.start(i)

    async def run_upload(
        self,
        i: Interaction,
        account: HoyoAccount,
        source: GachaImportSource,
        file: discord.Attachment,
    ) -> None:
        locale = await get_locale(i)
        embed = DefaultEmbed(
            locale,
            i.client.translator,
            title=LocaleStr(key="gacha_import_loading_embed_title"),
            description=LocaleStr(
                key="gacha_import_loading_embed_description", loading_emoji=LOADING
            ),
        ).add_acc_info(account)
        await i.response.send_message(embed=embed)

        try:
            if source is GachaImportSource.STAR_RAIL_STATION:
                count = await self._srs_import(i, account=account, file=file)
            elif source is GachaImportSource.ZZZ_RNG_MOE:
                count = await self._zzz_rng_moe_import(i, account=account, file=file)
            elif source is GachaImportSource.STAR_DB:
                count = await self._stardb_import(i, account=account, file=file)
            elif source is GachaImportSource.UIGF:
                count = await self._uigf_import(i, account=account, file=file)
            else:  # SRGF
                count = await self._srgf_import(i, account=account, file=file)
        except Exception as e:
            error_embed, _ = get_error_embed(e, locale, i.client.translator)
            await i.edit_original_response(embed=error_embed)
        else:
            embed = DefaultEmbed(
                locale,
                i.client.translator,
                title=LocaleStr(key="gacha_import_success_title"),
                description=LocaleStr(key="gacha_import_success_message", count=count),
            ).add_acc_info(account)
            await i.edit_original_response(embed=embed)

    async def run_view(self, i: Interaction, account: HoyoAccount) -> None:
        locale = await get_locale(i)
        view = ViewGachaLogView(
            account, author=i.user, locale=locale, translator=i.client.translator
        )
        await view.start(i)

    async def run_manage(self, i: Interaction, account: HoyoAccount) -> None:
        locale = await get_locale(i)
        view = GachaLogManageView(
            account, author=i.user, locale=locale, translator=i.client.translator
        )
        await view.start(i)
