from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

import orjson
import pandas as pd

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import UIGF_GAME_KEYS
from hoyo_buddy.db import GachaHistory, HoyoAccount, get_dyk, get_locale, update_gacha_nums
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import LOADING
from hoyo_buddy.enums import GachaImportSource, Game
from hoyo_buddy.exceptions import (
    AccountGameMismatchError,
    FeatureNotImplementedError,
    InvalidFileExtError,
    NoGachaLogFoundError,
    UIDMismatchError,
)
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.hoyo.clients.hakushin import HakushinZZZClient
from hoyo_buddy.hoyo.clients.yatta import YattaAPIClient
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import (
    SRGFRecord,
    StarDBRecord,
    StarRailStationRecord,
    StarwardZZZRecord,
    UIGFRecord,
    ZZZRngMoeRecord,
)
from hoyo_buddy.ui.hoyo.gacha.import_ import GachaImportView
from hoyo_buddy.ui.hoyo.gacha.manage import GachaLogManageView
from hoyo_buddy.ui.hoyo.gacha.view import ViewGachaLogView
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    import discord

    from hoyo_buddy.types import Interaction


class GachaCommand:
    @staticmethod
    def _validate_file_ext(file: discord.Attachment, accept_ext: str) -> None:
        extension = file.filename.split(".")[-1]
        if extension != accept_ext:
            raise InvalidFileExtError(accept_ext)

    @staticmethod
    async def _uigf_fill_item_rarities(
        records: list[dict[str, Any]], game: Game
    ) -> list[dict[str, Any]]:
        if game is Game.GENSHIN:
            api = AmbrAPIClient()
        elif game is Game.STARRAIL:
            api = YattaAPIClient()
        elif game is Game.ZZZ:
            api = HakushinZZZClient()
        else:
            msg = f"Rarity fetching is not implemented for {game}"
            raise ValueError(msg)

        fetch_map = not all("rank_type" in record for record in records)
        if fetch_map:
            async with api:
                rarity_map = await api.fetch_rarity_map()

            for record in records:
                if "rank_type" in record:
                    continue

                record["rank_type"] = rarity_map[record["item_id"]]

        return records

    @classmethod
    async def _srs_import(
        cls, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """Star Rail Station import."""
        cls._validate_file_ext(file, "csv")

        if account.game is not Game.STARRAIL:
            raise AccountGameMismatchError(Game.STARRAIL)

        bytes_ = await file.read()
        records_df = await i.client.loop.run_in_executor(
            i.client.executor, pd.read_csv, io.BytesIO(bytes_)
        )
        data = records_df.to_dict(orient="records")
        records = [
            StarRailStationRecord(**{str(k): v for k, v in record.items()}) for record in data
        ]
        records.sort(key=lambda x: x.id)

        before = await GachaHistory.get_wish_count(account)
        await GachaHistory.bulk_create(
            [
                GachaHistory(
                    wish_id=record.id,
                    rarity=record.rarity,
                    item_id=record.item_id,
                    banner_type=record.banner_type,
                    account=account,
                    time=record.time,
                    banner_id=None,
                    game=Game.STARRAIL,
                )
                for record in records
            ]
        )
        after = await GachaHistory.get_wish_count(account)

        return after - before

    @classmethod
    async def _zzz_rng_moe_import(
        cls, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """zzz.rng.moe import."""
        cls._validate_file_ext(file, "json")

        if account.game is not Game.ZZZ:
            raise AccountGameMismatchError(Game.ZZZ)

        bytes_ = await file.read()
        data = await i.client.loop.run_in_executor(i.client.executor, orjson.loads, bytes_)
        first_profile = next(iter(data["data"]["profiles"].values()), None)
        if first_profile is None:
            raise NoGachaLogFoundError

        uid = str(first_profile["bindUid"] or account.uid)
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
                    for record in first_profile["stores"]["0"]["items"][gacha_type]
                ]
            )
        records.sort(key=lambda x: x.id)

        before = await GachaHistory.get_wish_count(account)
        await GachaHistory.bulk_create(
            [
                GachaHistory(
                    wish_id=record.id,
                    rarity=record.rarity,
                    item_id=record.item_id,
                    banner_type=record.banner_type,
                    account=account,
                    time=record.time,
                    banner_id=None,
                    game=Game.ZZZ,
                )
                for record in records
            ]
        )
        after = await GachaHistory.get_wish_count(account)
        return after - before

    @classmethod
    async def _stardb_import(
        cls, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """stardb import."""
        cls._validate_file_ext(file, "json")

        bytes_ = await file.read()
        data = await i.client.loop.run_in_executor(i.client.executor, orjson.loads, bytes_)

        if account.game is Game.STARRAIL:
            return await cls._stardb_hsr_import(account, data)
        if account.game is Game.GENSHIN:
            return await cls._stardb_gi_import(account, data)
        if account.game is Game.ZZZ:
            return await cls._stardb_zzz_import(account, data)

        raise FeatureNotImplementedError(game=account.game)

    @staticmethod
    async def _stardb_hsr_import(account: HoyoAccount, data: dict[str, Any]) -> int:
        if account.game is not Game.STARRAIL:
            raise AccountGameMismatchError(Game.STARRAIL)

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
            records.sort(key=lambda x: x.id)

            if records:
                # Fetch rarity map with Yatta API
                async with YattaAPIClient() as client:
                    rarity_map = await client.fetch_rarity_map()

                before = await GachaHistory.get_wish_count(account)
                await GachaHistory.bulk_create(
                    [
                        GachaHistory(
                            wish_id=record.id,
                            rarity=rarity_map[record.item_id],
                            item_id=record.item_id,
                            banner_type=record.banner_type,
                            account=account,
                            time=record.time,
                            banner_id=None,
                            game=Game.STARRAIL,
                        )
                        for record in records
                    ]
                )
                after = await GachaHistory.get_wish_count(account)
                return after - before

        return 0

    @staticmethod
    async def _stardb_gi_import(account: HoyoAccount, data: dict[str, Any]) -> int:
        if account.game is not Game.GENSHIN:
            raise AccountGameMismatchError(Game.GENSHIN)

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
            records.sort(key=lambda x: x.id)

            if records:
                # Fetch rarity map with Ambr API
                async with AmbrAPIClient() as client:
                    rarity_map = await client.fetch_rarity_map()

                before = await GachaHistory.get_wish_count(account)
                await GachaHistory.bulk_create(
                    [
                        GachaHistory(
                            wish_id=record.id,
                            rarity=rarity_map[record.item_id],
                            item_id=record.item_id,
                            banner_type=record.banner_type,
                            account=account,
                            time=record.time,
                            banner_id=None,
                            game=Game.GENSHIN,
                        )
                        for record in records
                    ]
                )
                after = await GachaHistory.get_wish_count(account)
                return after - before

        return 0

    @staticmethod
    async def _stardb_zzz_import(account: HoyoAccount, data: dict[str, Any]) -> int:
        if account.game is not Game.ZZZ:
            raise AccountGameMismatchError(Game.ZZZ)

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
            records.sort(key=lambda x: x.id)

            if records:
                # Fetch rarity map with Hakushin API
                async with HakushinZZZClient() as client:
                    rarity_map = await client.fetch_rarity_map()

                before = await GachaHistory.get_wish_count(account)
                await GachaHistory.bulk_create(
                    [
                        GachaHistory(
                            wish_id=record.id,
                            rarity=rarity_map[record.item_id],
                            item_id=record.item_id,
                            banner_type=record.banner_type,
                            account=account,
                            time=record.time,
                            banner_id=None,
                            game=Game.ZZZ,
                        )
                        for record in records
                    ]
                )
                after = await GachaHistory.get_wish_count(account)
                return after - before

        return 0

    @classmethod
    async def _uigf_import(
        cls, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """UIGF import."""
        cls._validate_file_ext(file, "json")

        bytes_ = await file.read()
        data = await i.client.loop.run_in_executor(i.client.executor, orjson.loads, bytes_)

        # Determine UIGF v4.0
        version: str | None = data["info"].get("version", data["info"].get("uigf_version"))
        if version is None:
            msg = "Cannot determine UIGF version"
            raise ValueError(msg)

        is_v4 = version == "v4.0"

        if is_v4:
            game_data = next(
                (d for d in data[UIGF_GAME_KEYS[account.game]] if int(d["uid"]) == account.uid),
                None,
            )
            if game_data is None:
                raise UIDMismatchError(account.uid)

            tz_hour = game_data["timezone"]
            records = await cls._uigf_fill_item_rarities(game_data["list"], account.game)
            records = [UIGFRecord(timezone=tz_hour, **record) for record in records]
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

            if not all(record["item_id"] for record in data["list"]):
                # Fetch item IDs
                client = AmbrAPIClient(session=i.client.session)
                item_ids = await client.fetch_item_name_to_id_map()

                for record in data["list"]:
                    item_id = item_ids.get(record["name"])
                    if item_id is None:
                        msg = f"Cannot find item ID for {record['name']}, is this an invalid item?"
                        raise ValueError(msg)
                    record["item_id"] = item_id

            records = await cls._uigf_fill_item_rarities(data["list"], account.game)
            records = [UIGFRecord(timezone=tz_hour, **record) for record in records]

        records.sort(key=lambda x: x.id)

        before = await GachaHistory.get_wish_count(account)
        await GachaHistory.bulk_create(
            [
                GachaHistory(
                    wish_id=record.id,
                    rarity=record.rarity,
                    item_id=record.item_id,
                    banner_type=record.banner_type,
                    account=account,
                    time=record.time,
                    banner_id=None,
                    game=account.game,
                )
                for record in records
            ]
        )
        after = await GachaHistory.get_wish_count(account)
        return after - before

    @classmethod
    async def _srgf_import(
        cls, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """SRGF import."""
        cls._validate_file_ext(file, "json")

        if account.game is not Game.STARRAIL:
            raise AccountGameMismatchError(Game.STARRAIL)

        bytes_ = await file.read()
        data = await i.client.loop.run_in_executor(i.client.executor, orjson.loads, bytes_)

        uid = str(data["info"]["uid"])
        if uid != str(account.uid):
            raise UIDMismatchError(uid)

        tz_hour = data["info"]["region_time_zone"]
        records = [SRGFRecord(timezone=tz_hour, **record) for record in data["list"]]
        records.sort(key=lambda x: x.id)

        before = await GachaHistory.get_wish_count(account)
        await GachaHistory.bulk_create(
            [
                GachaHistory(
                    wish_id=record.id,
                    rarity=record.rarity,
                    item_id=record.item_id,
                    banner_type=record.banner_type,
                    account=account,
                    time=record.time,
                    banner_id=None,
                    game=Game.STARRAIL,
                )
                for record in records
            ]
        )
        after = await GachaHistory.get_wish_count(account)
        return after - before

    @classmethod
    async def _starward_zzz_import(
        cls, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """Starward Launcher ZZZ import."""
        cls._validate_file_ext(file, "json")

        if account.game is not Game.ZZZ:
            raise AccountGameMismatchError(Game.ZZZ)

        bytes_ = await file.read()
        data = await i.client.loop.run_in_executor(i.client.executor, orjson.loads, bytes_)

        uid = str(data["info"]["uid"])
        if uid != str(account.uid):
            raise UIDMismatchError(uid)

        tz_hour = data["info"]["region_time_zone"]
        records = [StarwardZZZRecord(tz_hour=tz_hour, **record) for record in data["list"]]
        records.sort(key=lambda x: x.id)

        before = await GachaHistory.get_wish_count(account)
        await GachaHistory.bulk_create(
            [
                GachaHistory(
                    wish_id=record.id,
                    rarity=record.rarity,
                    item_id=record.item_id,
                    banner_type=record.banner_type,
                    account=account,
                    time=record.time,
                    banner_id=None,
                    game=Game.ZZZ,
                )
                for record in records
            ]
        )
        after = await GachaHistory.get_wish_count(account)

        return after - before

    @staticmethod
    async def run_import(i: Interaction, account: HoyoAccount) -> None:
        locale = await get_locale(i)
        view = GachaImportView(account, author=i.user, locale=locale)
        await view.start(i)

    @classmethod
    async def run_upload(
        cls,
        i: Interaction,
        account: HoyoAccount,
        source: GachaImportSource,
        file: discord.Attachment,
    ) -> None:
        locale = await get_locale(i)
        embed = DefaultEmbed(
            locale,
            title=LocaleStr(key="gacha_import_loading_embed_title"),
            description=LocaleStr(
                key="gacha_import_loading_embed_description", loading_emoji=LOADING
            ),
        ).add_acc_info(account)
        await i.response.send_message(embed=embed, content=await get_dyk(i), ephemeral=ephemeral(i))

        try:
            if source is GachaImportSource.STAR_RAIL_STATION:
                count = await cls._srs_import(i, account=account, file=file)
            elif source is GachaImportSource.ZZZ_RNG_MOE:
                count = await cls._zzz_rng_moe_import(i, account=account, file=file)
            elif source is GachaImportSource.STAR_DB:
                count = await cls._stardb_import(i, account=account, file=file)
            elif source is GachaImportSource.UIGF:
                count = await cls._uigf_import(i, account=account, file=file)
            elif source is GachaImportSource.STARWARD_ZZZ:
                count = await cls._starward_zzz_import(i, account=account, file=file)
            elif source is GachaImportSource.SRGF:
                count = await cls._srgf_import(i, account=account, file=file)
            else:
                msg = f"Unsupported GachaImportSource: {source}"
                raise ValueError(msg)
        except Exception as e:
            error_embed, _ = get_error_embed(e, locale)
            await i.edit_original_response(embed=error_embed)
        else:
            await update_gacha_nums(i.client.pool, account=account)

            embed = DefaultEmbed(
                locale,
                title=LocaleStr(key="gacha_import_success_title"),
                description=LocaleStr(key="gacha_import_success_message", count=count),
            ).add_acc_info(account)
            await i.edit_original_response(embed=embed)

    @staticmethod
    async def run_view(i: Interaction, account: HoyoAccount) -> None:
        locale = await get_locale(i)
        view = ViewGachaLogView(account, author=i.user, locale=locale)
        await view.start(i)

    @staticmethod
    async def run_manage(i: Interaction, account: HoyoAccount) -> None:
        locale = await get_locale(i)
        view = GachaLogManageView(account, author=i.user, locale=locale)
        await view.start(i)
