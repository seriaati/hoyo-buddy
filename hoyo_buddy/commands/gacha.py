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
from hoyo_buddy.db.models import GachaHistory, HoyoAccount, get_dyk, get_locale, update_gacha_nums
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import LOADING
from hoyo_buddy.enums import GachaImportSource, Game
from hoyo_buddy.exceptions import (
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
    UIGFRecord,
    ZZZRngMoeRecord,
)
from hoyo_buddy.ui.hoyo.gacha.import_ import GachaImportView
from hoyo_buddy.ui.hoyo.gacha.manage import GachaLogManageView
from hoyo_buddy.ui.hoyo.gacha.view import ViewGachaLogView
from hoyo_buddy.utils import ephemeral, get_item_ids

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

        async with api:
            for record in records:
                if "rank_type" in record:
                    continue
                record["rank_type"] = await api.fetch_item_rarity(str(record["item_id"]))

        return records

    async def _srs_import(
        self, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """Star Rail Station import."""
        self._validate_file_ext(file, "csv")

        bytes_ = await file.read()
        records_df = await i.client.loop.run_in_executor(
            i.client.executor, pd.read_csv, io.BytesIO(bytes_)
        )
        data: list[dict[str, Any]] = records_df.to_dict(orient="records")  # pyright: ignore[reportAssignmentType]
        records = [StarRailStationRecord(**record) for record in data]
        records.sort(key=lambda x: x.id)

        count = 0

        for record in records:
            created = await GachaHistory.create(
                wish_id=record.id,
                rarity=record.rarity,
                item_id=record.item_id,
                banner_type=record.banner_type,
                account=account,
                time=record.time,
            )
            if created:
                count += 1

        return count

    async def _zzz_rng_moe_import(
        self, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """zzz.rng.moe import."""
        self._validate_file_ext(file, "json")

        bytes_ = await file.read()
        data = await i.client.loop.run_in_executor(i.client.executor, orjson.loads, bytes_)
        first_profile = next(iter(data["data"]["profiles"].values()), None)
        if first_profile is None:
            raise NoGachaLogFoundError

        uid = str(first_profile["bindUid"])
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

        count = 0

        for record in records:
            created = await GachaHistory.create(
                wish_id=record.id,
                rarity=record.rarity + 1,
                item_id=record.item_id,
                banner_type=record.banner_type,
                account=account,
                time=record.time,
            )
            if created:
                count += 1

        return count

    async def _stardb_import(
        self, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """stardb import."""
        self._validate_file_ext(file, "json")

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
            records.sort(key=lambda x: x.id)

            if records:
                # Fetch rarity map with Yatta API
                async with yatta.YattaAPI() as api:
                    characters = await api.fetch_characters()
                    lcs = await api.fetch_light_cones()

                rarity_map: dict[int, int] = {
                    character.id: character.rarity for character in characters
                } | {lc.id: lc.rarity for lc in lcs}

                count = 0

                for record in records:
                    created = await GachaHistory.create(
                        wish_id=record.id,
                        rarity=rarity_map[record.item_id],
                        item_id=record.item_id,
                        banner_type=record.banner_type,
                        account=account,
                        time=record.time,
                    )
                    if created:
                        count += 1

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
            records.sort(key=lambda x: x.id)

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

                count = 0

                for record in records:
                    created = await GachaHistory.create(
                        wish_id=record.id,
                        rarity=rarity_map[record.item_id],
                        item_id=record.item_id,
                        banner_type=record.banner_type,
                        account=account,
                        time=record.time,
                    )
                    if created:
                        count += 1

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
            records.sort(key=lambda x: x.id)

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

                count = 0

                for record in records:
                    created = await GachaHistory.create(
                        wish_id=record.id,
                        rarity=rarity_map[record.item_id],
                        item_id=record.item_id,
                        banner_type=record.banner_type,
                        account=account,
                        time=record.time,
                    )
                    if created:
                        count += 1

                return count

        return 0

    async def _uigf_import(
        self, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """UIGF import."""
        self._validate_file_ext(file, "json")

        bytes_ = await file.read()
        data = await i.client.loop.run_in_executor(i.client.executor, orjson.loads, bytes_)

        # Determine UIGF v4.0
        version = data["info"].get("version", data["info"]["uigf_version"])
        is_v4 = version == "v4.0"

        if is_v4:
            game_data = next(
                (d for d in data[UIGF_GAME_KEYS[account.game]] if int(d["uid"]) == account.uid),
                None,
            )
            if game_data is None:
                raise UIDMismatchError(account.uid)

            tz_hour = game_data["timezone"]
            records = await self._uigf_fill_item_rarities(game_data["list"], account.game)
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
                item_ids = await get_item_ids(
                    i.client.session,
                    item_names=[record["name"] for record in data["list"]],
                    lang=data["info"]["lang"],
                )

                for record in data["list"]:
                    record["item_id"] = item_ids[record["name"]]

            records = await self._uigf_fill_item_rarities(data["list"], account.game)
            records = [UIGFRecord(timezone=tz_hour, **record) for record in records]

        records.sort(key=lambda x: x.id)

        count = 0

        for record in records:
            created = await GachaHistory.create(
                wish_id=record.id,
                rarity=record.rarity,
                item_id=record.item_id,
                banner_type=record.banner_type,
                account=account,
                time=record.time,
            )
            if created:
                count += 1

        return count

    async def _srgf_import(
        self, i: Interaction, *, account: HoyoAccount, file: discord.Attachment
    ) -> int:
        """SRGF import."""
        self._validate_file_ext(file, "json")

        bytes_ = await file.read()
        data = await i.client.loop.run_in_executor(i.client.executor, orjson.loads, bytes_)

        uid = str(data["info"]["uid"])
        if uid != str(account.uid):
            raise UIDMismatchError(uid)

        tz_hour = data["info"]["region_time_zone"]
        records = [SRGFRecord(timezone=tz_hour, **record) for record in data["list"]]
        records.sort(key=lambda x: x.id)

        count = 0

        for record in records:
            created = await GachaHistory.create(
                wish_id=record.id,
                rarity=record.rarity,
                item_id=record.item_id,
                banner_type=record.banner_type,
                account=account,
                time=record.time,
            )
            if created:
                count += 1

        return count

    async def run_import(self, i: Interaction, account: HoyoAccount) -> None:
        locale = await get_locale(i)
        view = GachaImportView(account, author=i.user, locale=locale)
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
            title=LocaleStr(key="gacha_import_loading_embed_title"),
            description=LocaleStr(
                key="gacha_import_loading_embed_description", loading_emoji=LOADING
            ),
        ).add_acc_info(account)
        await i.response.send_message(embed=embed, content=await get_dyk(i), ephemeral=ephemeral(i))

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

    async def run_view(self, i: Interaction, account: HoyoAccount) -> None:
        locale = await get_locale(i)
        view = ViewGachaLogView(account, author=i.user, locale=locale)
        await view.start(i)

    async def run_manage(self, i: Interaction, account: HoyoAccount) -> None:
        locale = await get_locale(i)
        view = GachaLogManageView(account, author=i.user, locale=locale)
        await view.start(i)
