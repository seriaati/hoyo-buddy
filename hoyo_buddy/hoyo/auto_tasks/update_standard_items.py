from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, ClassVar

from loguru import logger

from hoyo_buddy.constants import STANDARD_ITEMS_FILENAME
from hoyo_buddy.db.models import JSONFile
from hoyo_buddy.enums import Game
from hoyo_buddy.utils import capture_exception

if TYPE_CHECKING:
    import aiohttp

GACHA_INFO_URL = "https://operation-webstatic.hoyoverse.com/gacha_info"
UIGF_DICT_URL = "https://api.uigf.org/dict/{game}/en.json"

GAME_BIZ_REGIONS: dict[Game, tuple[str, str]] = {
    Game.GENSHIN: ("hk4e", "os_asia"),
    Game.STARRAIL: ("hkrpg", "prod_official_asia"),
    Game.ZZZ: ("nap", "prod_gf_jp"),
}
UIGF_GAMES: dict[Game, str] = {Game.GENSHIN: "genshin", Game.STARRAIL: "starrail", Game.ZZZ: "zzz"}
STANDARD_GACHA_TYPES: dict[Game, set[int]] = {
    Game.GENSHIN: {200},
    Game.STARRAIL: {1},
    Game.ZZZ: {1001},
}
LOSE_POOL_GACHA_TYPES: dict[Game, set[int]] = {
    Game.STARRAIL: {11, 12, 21, 22},
    Game.ZZZ: {2001, 2002, 3001, 3002, 12002, 13002},
}
STANDARD_POOL_FIELDS = ("r5_prob_list", "items_avatar_star_5", "items_light_cone_star_5")
LOSE_POOL_FIELDS = (
    "items_replace_avatar_star_5",
    "items_replace_light_cone_star_5",
    "s_group_customize_items",
)


class UpdateStandardItems:
    """Update the standard banner item lists from the official gacha_info endpoints.

    Fetches the standard banner pools plus the items obtainable when losing 50/50
    (HSR Celestial Invitation, ZZZ customizable S-rank pool) and merges them into
    the standard items JSON file used for win rate calculations.
    """

    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    async def execute(cls, session: aiohttp.ClientSession) -> None:
        if cls._lock.locked():
            return

        async with cls._lock:
            try:
                data: dict[str, list[int]] = await JSONFile.read(
                    STANDARD_ITEMS_FILENAME, default={}
                )

                for game in GAME_BIZ_REGIONS:
                    try:
                        item_ids = await cls._fetch_game_items(session, game)
                    except Exception as e:
                        logger.warning(f"Failed to fetch standard items for {game}")
                        capture_exception(e)
                        continue

                    # Items are only ever added to standard pools, never removed,
                    # so merging keeps the data correct even if a fetch is incomplete.
                    merged = set(data.get(game.value, [])) | item_ids
                    data[game.value] = sorted(merged)
                    logger.info(f"Updated standard items for {game}, total {len(merged)}")

                await JSONFile.write(STANDARD_ITEMS_FILENAME, data)
            except Exception as e:
                capture_exception(e)

    @staticmethod
    async def _fetch_json(session: aiohttp.ClientSession, url: str) -> Any:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    @classmethod
    async def _fetch_game_items(cls, session: aiohttp.ClientSession, game: Game) -> set[int]:
        biz, region = GAME_BIZ_REGIONS[game]
        list_data = await cls._fetch_json(
            session, f"{GACHA_INFO_URL}/{biz}/{region}/gacha/list.json"
        )
        uigf_dict: dict[str, int] = await cls._fetch_json(
            session, UIGF_DICT_URL.format(game=UIGF_GAMES[game])
        )
        name_to_id = {name.lower(): item_id for name, item_id in uigf_dict.items()}

        item_ids: set[int] = set()
        for banner in list_data["data"]["list"]:
            if banner["gacha_type"] in STANDARD_GACHA_TYPES[game]:
                fields = STANDARD_POOL_FIELDS
            elif banner["gacha_type"] in LOSE_POOL_GACHA_TYPES.get(game, set()):
                fields = LOSE_POOL_FIELDS
            else:
                continue

            detail = await cls._fetch_json(
                session, f"{GACHA_INFO_URL}/{biz}/{region}/{banner['gacha_id']}/en-us.json"
            )
            item_ids |= cls._extract_item_ids(detail, fields, name_to_id, game)

        return item_ids

    @staticmethod
    def _extract_item_ids(
        detail: dict[str, Any], fields: tuple[str, ...], name_to_id: dict[str, int], game: Game
    ) -> set[int]:
        item_ids: set[int] = set()

        for field in fields:
            for item in detail.get(field) or []:
                if item.get("is_up"):
                    continue

                # GI and some ZZZ endpoints obfuscate item ids, fall back to name lookup
                item_id: int = item.get("origin_item_id") or 0
                if item_id <= 0:
                    item_id = name_to_id.get(str(item.get("item_name", "")).lower(), 0)

                if item_id > 0:
                    item_ids.add(item_id)
                else:
                    logger.warning(
                        f"Cannot resolve standard item {item.get('item_name')!r} for {game}"
                    )

        return item_ids
