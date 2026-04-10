from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import aiohttp
import chompjs
from loguru import logger

from hoyo_buddy.constants import STANDARD_ITEMS
from hoyo_buddy.db.models import GachaHistory, HoyoAccount, JSONFile
from hoyo_buddy.enums import Game
from hoyo_buddy.models.gacha import GIBanner, HSRBanner, ZZZBanner

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


def get_gacha_icon(*, item_id: int, gacha_data: dict[str, dict[str, str]]) -> str:
    return gacha_data.get(str(item_id), {}).get("icon", "")


@dataclass
class GachaStatsResult:
    total_pulls: int
    five_star_pity: int
    four_star_pity: int
    total_five_stars: int
    total_four_stars: int
    avg_pulls_per_five_star: float
    avg_pulls_per_four_star: float
    fifty_fifty_wins: int
    fifty_fifty_total: int
    fifty_fifty_win_rate: float


async def calc_50_50_stats(*, account: HoyoAccount, banner_type: int) -> tuple[int, int]:
    five_stars = (
        await GachaHistory.filter(account=account, rarity=5, banner_type=banner_type)
        .order_by("wish_id")
        .only("item_id", "time", "banner_id")
    )
    if not five_stars:
        return 0, 0

    gi_banners: list[GIBanner] = []
    item_names: dict[int, str] = {}
    hsr_banners: list[HSRBanner] = []

    async with aiohttp.ClientSession() as session:
        if account.game is Game.GENSHIN:
            gi_banners = await fetch_gi_banners(session)
            gi_data: dict[str, dict[str, str]] = await JSONFile.read(
                "gi_gacha_data_en-us.json", default={}
            )
            item_names = {int(k): v["name"] for k, v in gi_data.items()}
        elif account.game is Game.STARRAIL:
            hsr_banners = await fetch_hsr_banners(session)

    is_standards: list[bool] = []
    for item in five_stars:
        if account.game is Game.GENSHIN:
            is_standard = check_gi_item_is_standard(item, gi_banners, item_names)
        elif account.game is Game.STARRAIL:
            is_standard = check_hsr_item_is_standard(item, hsr_banners)
        elif account.game is Game.ZZZ:
            is_standard = check_zzz_item_is_standard(item)
        else:
            logger.error(f"Unknown game for checking is_standard: {account.game}")
            continue

        is_standards.append(is_standard)

    status: list[Literal[50, 100]] = [50]
    wins = 0

    for i, is_standard in enumerate(is_standards):
        status.append(100 if is_standard else 50)
        if status[i] == 50 and not is_standard:
            wins += 1
    del status[-1]

    return wins, status.count(50)


async def calculate_gacha_stats(
    *,
    account_id: int,
    game: Game,  # noqa: ARG001
    banner_type: int,
) -> GachaStatsResult:
    account = await HoyoAccount.get(id=account_id)

    last_gacha = (
        await GachaHistory.filter(account=account, banner_type=banner_type).first().only("num")
    )
    last_gacha_num = last_gacha.num if last_gacha else 0

    last_five_star = (
        await GachaHistory.filter(account=account, banner_type=banner_type, rarity=5)
        .first()
        .only("num")
    )
    last_five_star_num = last_five_star.num if last_five_star else 0

    last_four_star = (
        await GachaHistory.filter(account=account, banner_type=banner_type, rarity=4)
        .first()
        .only("num")
    )
    last_four_star_num = last_four_star.num if last_four_star else 0

    five_star_pity = last_gacha_num - last_five_star_num
    four_star_pity = last_gacha_num - last_four_star_num

    total_pulls = await GachaHistory.filter(account=account, banner_type=banner_type).count()
    total_five_stars = await GachaHistory.filter(
        account=account, banner_type=banner_type, rarity=5
    ).count()
    total_four_stars = await GachaHistory.filter(
        account=account, banner_type=banner_type, rarity=4
    ).count()

    avg_pulls_per_five_star = total_pulls / total_five_stars if total_five_stars else 0.0
    avg_pulls_per_four_star = total_pulls / total_four_stars if total_four_stars else 0.0

    fifty_fifty_wins, fifty_fifty_total = await calc_50_50_stats(
        account=account, banner_type=banner_type
    )
    fifty_fifty_win_rate = fifty_fifty_wins / fifty_fifty_total if fifty_fifty_total else 0.0

    return GachaStatsResult(
        total_pulls=total_pulls,
        five_star_pity=five_star_pity,
        four_star_pity=four_star_pity,
        total_five_stars=total_five_stars,
        total_four_stars=total_four_stars,
        avg_pulls_per_five_star=avg_pulls_per_five_star,
        avg_pulls_per_four_star=avg_pulls_per_four_star,
        fifty_fifty_wins=fifty_fifty_wins,
        fifty_fifty_total=fifty_fifty_total,
        fifty_fifty_win_rate=fifty_fifty_win_rate,
    )
