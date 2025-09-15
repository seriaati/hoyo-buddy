from __future__ import annotations

import re
from typing import TYPE_CHECKING

import chompjs
from loguru import logger

from hoyo_buddy.constants import STANDARD_ITEMS
from hoyo_buddy.enums import Game
from hoyo_buddy.models.gacha import GIBanner, HSRBanner, ZZZBanner

if TYPE_CHECKING:
    import aiohttp

    from hoyo_buddy.db.models.gacha_history import GachaHistory

HSR_BANNER_URL = "https://starrailstation.com/api/v1/warp_config"
ZZZ_BANNER_URL = "https://zzz.rng.moe/api/v1/gacha/config?game=zzz"
GI_BANNER_URL = "https://raw.githubusercontent.com/MadeBaruna/paimon-moe-api/refs/heads/main/src/data/banners.ts"


async def fetch_hsr_banners(session: aiohttp.ClientSession) -> list[HSRBanner]:
    async with session.get(HSR_BANNER_URL) as resp:
        resp.raise_for_status()
        data = await resp.json()
        return [
            HSRBanner(id=int(banner_id), **banner)
            for banner_id, banner in data.get("config", {}).get("banners", {}).items()
        ]


async def fetch_zzz_banners(session: aiohttp.ClientSession) -> list[ZZZBanner]:
    async with session.get(ZZZ_BANNER_URL) as resp:
        resp.raise_for_status()
        data = await resp.json()
        return [
            ZZZBanner(id=int(banner_id), **banner)
            for banner_id, banner in data.get("data", {}).items()
        ]


async def fetch_gi_banners(session: aiohttp.ClientSession) -> list[GIBanner]:
    async with session.get(GI_BANNER_URL) as resp:
        resp.raise_for_status()
        content = await resp.text()

    pattern = r"export const banners: \{ \[key: number\]: Banner \} = (\{.*?\});"
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        logger.error("Failed to find banners in GI banner data")
        return []

    banners_str = match.group(1)

    banners_dict = chompjs.parse_js_object(banners_str)
    banners_dict = {int(k): v for k, v in banners_dict.items()}

    return [GIBanner(id=k, **v) for k, v in banners_dict.items()]


def check_zzz_item_is_standard(item: GachaHistory) -> bool:
    return item.item_id in STANDARD_ITEMS.get(Game.ZZZ, [])


def check_hsr_item_is_standard(item: GachaHistory, hsr_banners: list[HSRBanner]) -> bool:
    is_standard = item.item_id in STANDARD_ITEMS.get(Game.STARRAIL, [])
    for banner in hsr_banners:
        if item.banner_id == banner.id and item.item_id in banner.five_stars:
            return False
    return is_standard


def check_gi_item_is_standard(
    item: GachaHistory, gi_banners: list[GIBanner], item_names: dict[int, str]
) -> bool:
    is_standard = item.item_id in STANDARD_ITEMS.get(Game.GENSHIN, [])

    for banner in gi_banners:
        if banner.start_at <= item.time.replace(tzinfo=None) <= banner.end_at:
            five_star_item_ids = banner.get_five_star_item_ids(item_names)
            if item.item_id in five_star_item_ids:
                return False

    return is_standard
