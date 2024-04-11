import asyncio
import logging
from typing import TYPE_CHECKING

import genshin
from discord import Locale

from ...bot.error_handler import get_error_embed
from ...bot.translator import LocaleStr
from ...db.models import HoyoAccount
from ...enums import Game

if TYPE_CHECKING:
    import aiohttp

    from ...bot.bot import HoyoBuddy

LOGGER_ = logging.getLogger(__name__)
CODE_NUM_TO_SLEEP = 15
SLEEP_INTERVAL = 60 * 5


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

        accounts = await HoyoAccount.filter(auto_redeem=True)
        redeem_count = 0

        for account in accounts:
            if account.game is Game.GENSHIN:
                codes = genshin_codes
            elif account.game is Game.STARRAIL:
                codes = hsr_codes
            else:
                continue

            # filter out codes that have already been redeemed
            codes = [code for code in codes if code not in account.redeemed_codes]
            if not codes:
                continue

            await account.fetch_related("user", "user__settings")
            locale = account.user.settings.locale or Locale.american_english

            try:
                embed = await account.client.redeem_codes(
                    codes, locale=locale, translator=bot.translator, inline=True, blur=False
                )
                embed.set_footer(
                    text=LocaleStr(
                        "Turn off auto code redemption with /redeem", key="auto_redeem_footer"
                    )
                )
            except Exception as e:
                embed, recognized = get_error_embed(e, locale, bot.translator)
                embed.add_acc_info(account, blur=False)
                if not recognized:
                    bot.capture_exception(e)

                content = LocaleStr(
                    "An error occurred while performing automatic code redemption.\n"
                    "This feature can be disabled with </redeem>.\n",
                    key="auto_redeem_error.content",
                )
                await bot.dm_user(
                    account.user.id, embed=embed, content=content.translate(bot.translator, locale)
                )
            else:
                account.redeemed_codes.extend(codes)
                # remove duplicates
                account.redeemed_codes = list(set(account.redeemed_codes))
                await account.save(update_fields=("redeemed_codes",))

                await bot.dm_user(account.user.id, embed=embed)

                redeem_count += len(embed.fields)
                if redeem_count % CODE_NUM_TO_SLEEP == 0:
                    # Sleep every n codes to prevent rate limiting
                    await asyncio.sleep(SLEEP_INTERVAL)

        LOGGER_.info("Auto redeem task completed")
