from typing import TYPE_CHECKING

import akasha

from ...bot.translator import LocaleStr, Translator
from ...embeds import DefaultEmbed

if TYPE_CHECKING:
    from discord import Locale


async def get_user_calcs(uid: int) -> list[akasha.UserCalc]:
    async with akasha.AkashaAPI() as api:
        await api.get_user(uid)
        return await api.get_calculations_for_user(uid)


async def get_leaderboards(calculation_id: int) -> list[akasha.Leaderboard]:
    async with akasha.AkashaAPI() as api:
        return await api.get_leaderboards(calculation_id)


def get_akasha_profile_url(uid: str) -> str:
    return f"https://akasha.cv/profile/{uid}"


def get_embed(
    user_calc: akasha.UserCalc,
    _: list[akasha.Leaderboard],
    *,
    locale: "Locale",
    translator: Translator,
) -> DefaultEmbed:
    calc = user_calc.calculations[0]
    refinement_str = LocaleStr(key="refinement_indicator", r=calc.weapon.refinement).translate(
        translator, locale
    )

    embed = DefaultEmbed(
        title=calc.name,
        description=f"{calc.details}\n\n{calc.weapon.name} ({refinement_str})",
        locale=locale,
        translator=translator,
    )
    embed.set_author(name=user_calc.name)
    embed.set_thumbnail(url=user_calc.icon)

    return embed
