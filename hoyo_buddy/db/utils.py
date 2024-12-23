# pyright: reportAssignmentType=false

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from discord import Locale

from hoyo_buddy.enums import Game, LeaderboardType, Platform
from hoyo_buddy.l10n import translator

from .models import GachaHistory, HoyoAccount, Settings, User

if TYPE_CHECKING:
    import asyncpg

    from hoyo_buddy.models import Dismissible
    from hoyo_buddy.types import Interaction

__all__ = (
    "draw_locale",
    "get_dyk",
    "get_enable_dyk",
    "get_last_gacha_num",
    "get_locale",
    "get_num_since_last",
    "show_dismissible",
    "update_gacha_nums",
    "update_lb_ranks",
)


async def get_locale(i: Interaction) -> Locale:
    cache = i.client.cache
    key = f"{i.user.id}:lang"
    if await cache.exists(key):
        locale = await cache.get(key)
        return Locale(locale) if locale is not None else i.locale
    settings = await Settings.get(user_id=i.user.id).only("lang")
    locale = settings.locale or i.locale
    await cache.set(key, locale.value)
    return locale


async def get_enable_dyk(i: Interaction) -> bool:
    cache = i.client.cache
    key = f"{i.user.id}:dyk"
    if await cache.exists(key):
        return await cache.get(key)
    settings = await Settings.get(user_id=i.user.id).only("enable_dyk")
    await cache.set(key, settings.enable_dyk)
    return settings.enable_dyk


async def get_dyk(i: Interaction) -> str:
    enable_dyk = await get_enable_dyk(i)
    locale = await get_locale(i)
    if not enable_dyk:
        return ""
    return translator.get_dyk(locale)


async def get_last_gacha_num(
    account: HoyoAccount, *, banner: int, rarity: int | None = None, num_lt: int | None = None
) -> int:
    filter_kwrargs = {"account": account, "banner_type": banner}
    if rarity is not None:
        filter_kwrargs["rarity"] = rarity
    if num_lt is not None:
        filter_kwrargs["num__lt"] = num_lt

    last_gacha = await GachaHistory.filter(**filter_kwrargs).first().only("num")
    return last_gacha.num if last_gacha else 0


async def get_num_since_last(account: HoyoAccount, *, banner: int, num: int, rarity: int) -> int:
    """Return the number of pulls since the last 5 or 4 star pull."""
    if rarity == 3:
        return 0
    last_num = await get_last_gacha_num(account, banner=banner, rarity=rarity, num_lt=num)
    return num - last_num


UPDATE_NUM_SQL = """
WITH ranked_wishes AS (
  SELECT
    wish_id,
    banner_type,
    ROW_NUMBER() OVER (PARTITION BY banner_type ORDER BY wish_id) AS new_num
  FROM gachahistory
  WHERE account_id = $1
)
UPDATE gachahistory w
SET num = r.new_num
FROM ranked_wishes r
WHERE w.wish_id = r.wish_id
  AND w.account_id = $1;
"""

UPDATE_NUM_SINCE_LAST_SQL = """
WITH sorted_wishes AS (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY banner_type ORDER BY wish_id) AS row_num
  FROM gachahistory
  WHERE account_id = $1
),
previous_wishes AS (
  SELECT *,
         LAG(num) OVER (PARTITION BY banner_type, rarity ORDER BY row_num) AS prev_num
  FROM sorted_wishes
)
UPDATE gachahistory
SET num_since_last =
  CASE
    WHEN pw.prev_num IS NULL THEN pw.num - 1
    ELSE pw.num - pw.prev_num
  END
FROM previous_wishes pw
WHERE gachahistory.wish_id = pw.wish_id
  AND gachahistory.account_id = $1;
"""


async def update_gacha_nums(pool: asyncpg.Pool, *, account: HoyoAccount) -> None:
    """Update the num and num_since_last fields of the gacha histories."""
    async with pool.acquire() as conn:
        await conn.execute(UPDATE_NUM_SQL, account.id)
        await conn.execute(UPDATE_NUM_SINCE_LAST_SQL, account.id)


UPDATE_LB_RANK_SQL = """
WITH ranked_leaderboard AS (
  SELECT
    uid,
    type,
    game,
    value,
    ROW_NUMBER() OVER (
      PARTITION BY type, game
      ORDER BY value {order}
    ) AS new_rank
  FROM Leaderboard
  WHERE game = $1 AND type = $2
)
UPDATE Leaderboard l
SET rank = r.new_rank
FROM ranked_leaderboard r
WHERE l.uid = r.uid
  AND l.type = r.type
  AND l.game = r.game;
"""


async def update_lb_ranks(
    pool: asyncpg.Pool, *, game: Game, type_: LeaderboardType, order: Literal["ASC", "DESC"]
) -> None:
    """Update the ranks of the leaderboards."""
    async with pool.acquire() as conn:
        await conn.execute(UPDATE_LB_RANK_SQL.format(order=order), game, type_)


def draw_locale(locale: Locale, account: HoyoAccount) -> Locale:
    if account.platform is Platform.MIYOUSHE:
        return Locale.chinese
    return locale


async def show_dismissible(i: Interaction, dismissible: Dismissible) -> None:
    user = await User.get(id=i.user.id)
    if dismissible.id in user.dismissibles:
        return

    locale = await get_locale(i)
    embed = dismissible.to_embed(locale)

    if i.response.is_done():
        await i.followup.send(embed=embed, ephemeral=True)
    else:
        await i.response.send_message(embed=embed, ephemeral=True)

    user.dismissibles.append(dismissible.id)
    await user.save(update_fields=("dismissibles",))
