from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, Literal

import genshin
from loguru import logger

from hoyo_buddy.constants import (
    BANNER_FIVE_STAR_GUARANTEE_NUMS,
    BANNER_FIVE_STAR_SOFT_PITY_NUMS,
    BANNER_WIN_RATE_TITLES,
    locale_to_hoyo_lang,
)
from hoyo_buddy.db import GachaHistory, GachaStats, JSONFile, get_last_gacha_num
from hoyo_buddy.enums import FiftyFiftyResult, GachaItemKind, Game
from hoyo_buddy.exceptions import NoGachaLogFoundError
from hoyo_buddy.l10n import BANNER_TYPE_NAMES
from hoyo_buddy.models.gacha_summary import GachaRank, GachaSummary, GachaSummaryItem
from hoyo_buddy.utils.gacha import calc_five_star_results

if TYPE_CHECKING:
    import asyncpg

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.enums import Locale

type GlobalStat = Literal[
    "lifetime_pulls", "avg_5star_pulls", "avg_4star_pulls", "avg_3star_pulls", "win_rate"
]

GET_RANKING_SQL = """
SELECT
    ranked.rank,
    (SELECT COUNT(*) FROM gachastats WHERE game = $1 AND banner_type = $3) AS total_rows
FROM (
    SELECT
        account_id,
        ROW_NUMBER() OVER (ORDER BY {row} {order}) as rank
    FROM gachastats
    WHERE game = $1 AND banner_type = $3
) ranked
WHERE account_id = $2;
"""

RANK_ORDERS: Final[dict[GlobalStat, Literal["ASC", "DESC"]]] = {
    "lifetime_pulls": "DESC",
    "avg_5star_pulls": "ASC",
    "avg_4star_pulls": "ASC",
    "avg_3star_pulls": "ASC",
    "win_rate": "DESC",
}

GACHA_DATA_PREFIXES: Final[dict[Game, str]] = {
    Game.GENSHIN: "gi",
    Game.STARRAIL: "hsr",
    Game.ZZZ: "zzz",
}

PREVIOUS_ITEM_COUNT: Final[int] = 5


async def get_ranking(
    pool: asyncpg.Pool, *, account: HoyoAccount, stat: GlobalStat, banner_type: int
) -> GachaRank | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            GET_RANKING_SQL.format(row=stat, order=RANK_ORDERS[stat]),
            account.game.value,
            account.id,
            banner_type,
        )

    if row is None:
        return None
    rank, total = row
    if rank == 0 or total == 0:
        return None
    return GachaRank(rank=rank, total=total)


def get_item_kind(game: Game, item_id: int) -> GachaItemKind:
    if game is Game.GENSHIN:
        # Character IDs look like 10000089, weapon IDs like 11509
        return GachaItemKind.WEAPON if item_id < 1_000_000 else GachaItemKind.CHARACTER
    if game is Game.STARRAIL:
        # Character IDs look like 1310, light cone IDs like 23025
        return GachaItemKind.WEAPON if item_id >= 20000 else GachaItemKind.CHARACTER
    if game is Game.ZZZ:
        # Agent IDs look like 1091, W-engine IDs like 14109, bangboo IDs like 54001
        if item_id >= 50000:
            return GachaItemKind.BANGBOO
        return GachaItemKind.WEAPON if item_id >= 10000 else GachaItemKind.CHARACTER

    msg = f"Unsupported game: {game}"
    raise ValueError(msg)


async def fetch_player_avatar(account: HoyoAccount) -> str | None:
    """Fetch the in-game profile icon URL of the account."""
    client = account.client
    try:
        if account.game is Game.GENSHIN:
            user = await client.get_partial_genshin_user(account.uid)
            return user.info.in_game_avatar
        if account.game is Game.STARRAIL:
            return (await client.get_starrail_user(account.uid)).in_game_avatar
        if account.game is Game.ZZZ:
            return (await client.get_zzz_user(account.uid)).in_game_avatar
    except genshin.GenshinException as e:
        logger.warning(f"Failed to fetch in-game avatar for account {account.id}: {e}")
    return None


async def _count_pulls(account: HoyoAccount, **filters: Any) -> int:
    return await GachaHistory.filter(account=account, **filters).count()


async def _load_item_names(game: Game, locale: Locale) -> dict[int, str]:
    lang = locale_to_hoyo_lang(locale)
    data: dict[str, dict[str, str]] = await JSONFile.read(
        f"{GACHA_DATA_PREFIXES[game]}_gacha_data_{lang}.json", default={}
    )
    return {int(k): v["name"] for k, v in data.items() if "name" in v}


async def build_gacha_summary(
    account: HoyoAccount, *, banner_type: int, pool: asyncpg.Pool, locale: Locale, avatar_url: str
) -> GachaSummary:
    """Collect everything shown on the gacha log stats embed and summary card.

    Also updates the account's GachaStats row so global rankings stay current.
    """
    game = account.game

    lifetime_pulls = await _count_pulls(account)
    if lifetime_pulls == 0:
        raise NoGachaLogFoundError

    is_standard_ode = banner_type == genshin.models.MWBannerType.STANDARD and game is Game.GENSHIN

    # Bangboo channel pulls don't cost currency
    bangboo_channel_pulls = await _count_pulls(account, banner_type=5)
    lifetime_currency = (lifetime_pulls - bangboo_channel_pulls) * 160

    last_gacha_num = await get_last_gacha_num(account, banner=banner_type)

    # Five star pity
    if not is_standard_ode:
        last_five_star_num = await get_last_gacha_num(account, banner=banner_type, rarity=5)
        five_star_pity = last_gacha_num - last_five_star_num
        five_star_max_pity = BANNER_FIVE_STAR_GUARANTEE_NUMS[game][banner_type]
    else:
        last_five_star_num = 0
        five_star_pity = 0
        five_star_max_pity = 0

    # Four star pity
    last_four_star_num = await get_last_gacha_num(account, banner=banner_type, rarity=4)
    four_star_pity = last_gacha_num - last_four_star_num
    four_star_max_pity = 70 if is_standard_ode else 10
    if not is_standard_ode and four_star_pity > four_star_max_pity:
        four_star_pity = last_gacha_num - last_five_star_num

    # Three star pity
    if is_standard_ode:
        last_three_star_num = await get_last_gacha_num(account, banner=banner_type, rarity=3)
        three_star_pity = last_gacha_num - last_three_star_num
        three_star_max_pity = 5
        if three_star_pity > three_star_max_pity:
            three_star_pity = last_gacha_num - last_four_star_num
    else:
        three_star_pity = 0
        three_star_max_pity = 0

    banner_pulls = await _count_pulls(account, banner_type=banner_type)
    total_five_stars = await _count_pulls(account, banner_type=banner_type, rarity=5)
    total_four_stars = await _count_pulls(account, banner_type=banner_type, rarity=4)
    total_three_stars = await _count_pulls(account, banner_type=banner_type, rarity=3)
    avg_five_star_pulls = banner_pulls / total_five_stars if total_five_stars else 0.0
    avg_four_star_pulls = banner_pulls / total_four_stars if total_four_stars else 0.0
    avg_three_star_pulls = banner_pulls / total_three_stars if total_three_stars else 0.0

    is_bangboo_channel = banner_type == 5 and game is Game.ZZZ
    banner_currency = 0 if is_bangboo_channel else banner_pulls * 160

    win_rate_title = BANNER_WIN_RATE_TITLES[game].get(banner_type)
    five_star_results = await calc_five_star_results(account=account, banner_type=banner_type)
    results = [r for _, r in five_star_results]
    fifty_fifty_wins = results.count(FiftyFiftyResult.WON)
    fifty_fifty_total = fifty_fifty_wins + results.count(FiftyFiftyResult.LOST)

    await GachaStats.create_or_update(
        account=account,
        lifetime_pulls=lifetime_pulls,
        win_rate=fifty_fifty_wins / fifty_fifty_total if fifty_fifty_total else 0.0,
        avg_5star_pulls=avg_five_star_pulls,
        avg_4star_pulls=avg_four_star_pulls,
        avg_3star_pulls=avg_three_star_pulls,
        banner_type=banner_type,
    )

    async def rank(stat: GlobalStat) -> GachaRank | None:
        return await get_ranking(pool, account=account, stat=stat, banner_type=banner_type)

    item_names = await _load_item_names(game, locale)
    items = [
        GachaSummaryItem(
            item_id=history.item_id,
            name=item_names.get(history.item_id, str(history.item_id)),
            kind=get_item_kind(game, history.item_id),
            pulls=history.num_since_last,
            result=result if win_rate_title is not None else None,
            time=history.time,
        )
        for history, result in reversed(five_star_results[-(PREVIOUS_ITEM_COUNT + 1) :])
    ]

    return GachaSummary(
        game=game,
        banner_type=banner_type,
        banner_name=BANNER_TYPE_NAMES[game][banner_type].translate(locale),
        nickname=account.username,
        uid=account.uid,
        avatar_url=avatar_url,
        five_star_pity=five_star_pity,
        five_star_max_pity=five_star_max_pity,
        five_star_soft_pity=BANNER_FIVE_STAR_SOFT_PITY_NUMS[game].get(banner_type),
        four_star_pity=four_star_pity,
        four_star_max_pity=four_star_max_pity,
        win_rate_title=win_rate_title,
        guaranteed=bool(results) and results[-1] is FiftyFiftyResult.LOST,
        banner_pulls=banner_pulls,
        banner_currency=banner_currency,
        lifetime_pulls=lifetime_pulls,
        lifetime_currency=lifetime_currency,
        total_five_stars=total_five_stars,
        total_four_stars=total_four_stars,
        avg_five_star_pulls=avg_five_star_pulls,
        avg_four_star_pulls=avg_four_star_pulls,
        fifty_fifty_wins=fifty_fifty_wins,
        fifty_fifty_total=fifty_fifty_total,
        lifetime_rank=await rank("lifetime_pulls"),
        five_star_luck_rank=None if is_standard_ode else await rank("avg_5star_pulls"),
        four_star_luck_rank=await rank("avg_4star_pulls"),
        win_rate_rank=None if win_rate_title is None else await rank("win_rate"),
        latest=items[0] if items else None,
        previous=items[1:],
        is_standard_ode=is_standard_ode,
        three_star_pity=three_star_pity,
        three_star_max_pity=three_star_max_pity,
        total_three_stars=total_three_stars,
        avg_three_star_pulls=avg_three_star_pulls,
        three_star_luck_rank=await rank("avg_3star_pulls") if is_standard_ode else None,
    )
