import asyncio
import logging
from typing import TYPE_CHECKING

import genshin
from discord import Locale

from ...bot.translator import LocaleStr
from ...db.models import HoyoAccount
from ...enums import Game

if TYPE_CHECKING:
    import aiohttp

    from ...bot.bot import HoyoBuddy

LOGGER_ = logging.getLogger(__name__)
CODE_NUM_TO_SLEEP = 50
SLEEP_INTERVAL = 60


class AutoRedeem:
    @classmethod
    async def _get_codes(cls, session: "aiohttp.ClientSession", game: genshin.Game) -> list[str]:
        async with session.get(f"https://hoyo-codes.vercel.app/codes?game={game.value}") as resp:
            return (await resp.json())["codes"]

    @classmethod
    async def execute(cls, bot: "HoyoBuddy") -> None:
        LOGGER_.info("Starting auto redeem task")

        genshin_codes = await cls._get_codes(bot.session, genshin.Game.GENSHIN)
        hsr_codes = await cls._get_codes(bot.session, genshin.Game.STARRAIL)

        accounts = await HoyoAccount.filter(auto_redeem=True).prefetch_related(
            "user", "user__settings"
        )
        redeem_count = 0

        for account in accounts:
            locale = account.user.settings.locale or Locale.american_english

            if account.game is Game.GENSHIN:
                codes = genshin_codes
            elif account.game is Game.STARRAIL:
                codes = hsr_codes
            else:
                raise NotImplementedError

            # filter out codes that have already been redeemed
            codes = [code for code in codes if code not in account.redeemed_codes]
            if not codes:
                continue

            embed = await account.client.redeem_codes(
                codes, locale=locale, translator=bot.translator, inline=True
            )
            embed.set_footer(text=LocaleStr("Turn off auto code redemption in /redeem"))
            account.redeemed_codes.extend(codes)
            # remove duplicates
            account.redeemed_codes = list(set(account.redeemed_codes))
            await account.save(update_fields=("redeemed_codes"))

            await bot.dm_user(account.user.id, embed=embed)

            redeem_count += len(codes)
            if redeem_count % CODE_NUM_TO_SLEEP == 0:
                # Sleep every n codes to prevent rate limiting
                await asyncio.sleep(SLEEP_INTERVAL)

        LOGGER_.info("Auto redeem task completed, redeemed %d codes", redeem_count)
