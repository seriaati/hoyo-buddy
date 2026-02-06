# pyright: reportAssignmentType=false

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from loguru import logger
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q

from hoyo_buddy.constants import (
    NO_MASKED_LINK_GUILDS,
    PLATFORM_TO_REGION,
    ZZZ_AGENT_STAT_TO_DISC_SUBSTAT,
    ZZZ_DISC_SUBSTATS,
)
from hoyo_buddy.draw.card_data import CARD_DATA
from hoyo_buddy.enums import Game, LeaderboardType, Locale, Platform
from hoyo_buddy.l10n import translator
from hoyo_buddy.utils import contains_masked_link, get_template_num

from . import models

if TYPE_CHECKING:
    from collections.abc import Sequence

    import asyncpg
    import genshin

    from hoyo_buddy.types import Interaction

__all__ = (
    "build_account_query",
    "draw_locale",
    "get_dyk",
    "get_enable_dyk",
    "get_last_gacha_num",
    "get_locale",
    "get_num_since_last",
    "update_gacha_nums",
    "update_lb_ranks",
)


async def get_locale(i: Interaction) -> Locale:
    settings = await models.Settings.get_or_none(user_id=i.user.id)
    return (
        settings.locale or Locale.american_english
        if settings is not None
        else Locale.american_english
    )


async def get_enable_dyk(i: Interaction) -> bool:
    settings = await models.Settings.get_or_none(user_id=i.user.id)
    return settings.enable_dyk if settings is not None else True


async def get_dyk(i: Interaction) -> str:
    enable_dyk = await get_enable_dyk(i)
    locale = await get_locale(i)
    if not enable_dyk:
        return ""

    dyk = translator.get_dyk(locale)
    if i.guild is not None and contains_masked_link(dyk) and i.guild.id in NO_MASKED_LINK_GUILDS:
        return ""
    return dyk


async def get_last_gacha_num(
    account: models.HoyoAccount,
    *,
    banner: int,
    rarity: int | None = None,
    num_lt: int | None = None,
) -> int:
    filter_kwrargs = {"account": account, "banner_type": banner}
    if rarity is not None:
        filter_kwrargs["rarity"] = rarity
    if num_lt is not None:
        filter_kwrargs["num__lt"] = num_lt

    last_gacha = await models.GachaHistory.filter(**filter_kwrargs).first().only("num")
    return last_gacha.num if last_gacha else 0


async def get_num_since_last(
    account: models.HoyoAccount, *, banner: int, num: int, rarity: int
) -> int:
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
    WHEN pw.prev_num IS NULL THEN pw.num
    ELSE pw.num - pw.prev_num
  END
FROM previous_wishes pw
WHERE gachahistory.wish_id = pw.wish_id
  AND gachahistory.account_id = $1;
"""


async def update_gacha_nums(pool: asyncpg.Pool, *, account: models.HoyoAccount) -> None:
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


def draw_locale(locale: Locale, account: models.HoyoAccount) -> Locale:
    if account.platform is Platform.MIYOUSHE:
        return Locale.chinese
    return locale


def build_account_query(
    *,
    games: Sequence[Game] | None = None,
    region: genshin.Region | None = None,
    platform: Platform | None = None,
    user_id: int | None = None,
    **kwargs,
) -> Q:
    query = Q()
    if games is not None:
        query &= Q(game__in=games)
    if region is not None:
        query &= Q(region=region)
    if platform is not None:
        query &= Q(region=PLATFORM_TO_REGION[platform])
    if user_id is not None:
        query &= Q(user_id=user_id)
    if kwargs:
        query &= Q(**kwargs)
    return query


async def set_highlight_substats(
    *,
    agent_special_stat_map: dict[str, list[int]],
    card_settings: models.CardSettings,
    character_id: int,
) -> None:
    special_stat_ids = agent_special_stat_map.get(str(character_id), [])
    special_substat_ids = [
        ZZZ_AGENT_STAT_TO_DISC_SUBSTAT.get(stat_id) for stat_id in special_stat_ids
    ]

    hl_substats = [
        substat_id for _, substat_id, _ in ZZZ_DISC_SUBSTATS if substat_id in special_substat_ids
    ]
    card_settings.highlight_substats = hl_substats
    await card_settings.save(update_fields=("highlight_substats",))


async def get_card_settings(user_id: int, character_id: str, *, game: Game) -> models.CardSettings:
    card_settings = await models.CardSettings.get_or_none(
        user_id=user_id, character_id=character_id, game=game
    )
    if card_settings is None:
        card_settings = await models.CardSettings.get_or_none(
            user_id=user_id, character_id=character_id
        )

    if card_settings is None:
        user_settings = await models.Settings.get(user_id=user_id)
        templates = {
            Game.GENSHIN: user_settings.gi_card_temp,
            Game.STARRAIL: user_settings.hsr_card_temp,
            Game.ZZZ: user_settings.zzz_card_temp,
        }
        template = templates.get(game)
        if template is None:
            logger.error(
                f"Game {game!r} does not have its table column for default card template setting."
            )
            template = "hb1"

        dark_modes = {
            Game.GENSHIN: user_settings.gi_dark_mode,
            Game.STARRAIL: user_settings.hsr_dark_mode,
            Game.ZZZ: user_settings.zzz_dark_mode,
        }
        dark_mode = dark_modes.get(game)
        if dark_mode is None:
            logger.error(
                f"Game {game!r} does not have its table column for default dark mode setting."
            )
            dark_mode = False

        try:
            card_settings = await models.CardSettings.create(
                user_id=user_id,
                character_id=character_id,
                dark_mode=dark_mode,
                template=template,
                game=game,
            )
        except IntegrityError:
            card_settings = await models.CardSettings.get(
                user_id=user_id, character_id=character_id, game=game
            )
    elif card_settings.game is None:
        card_settings.game = game
        await card_settings.save(update_fields=("game",))

    return card_settings


def get_default_color(
    character_id: str, *, game: Game, template: str, dark_mode: bool, outfit_id: int | None
) -> str | None:
    try:
        if game is Game.ZZZ:
            key = character_id if outfit_id is None else f"{character_id}_{outfit_id}"
            template_num = get_template_num(template)

            if template_num == 2:
                try:
                    color = CARD_DATA.zzz2[key].color
                except KeyError:
                    return CARD_DATA.zzz[key].color

                if color is None:
                    return CARD_DATA.zzz[key].color
                return color

            return CARD_DATA.zzz[key].color

        if game is Game.STARRAIL:
            color = CARD_DATA.hsr[character_id].primary
            if dark_mode:
                return CARD_DATA.hsr[character_id].primary_dark or color
            return color
    except KeyError:
        return None

    return None
