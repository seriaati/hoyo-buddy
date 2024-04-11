import asyncio
import logging
from typing import TYPE_CHECKING, ClassVar

import genshin
from discord import Locale

from ...bot.error_handler import get_error_embed
from ...bot.translator import LocaleStr
from ...db.models import HoyoAccount
from ...enums import Game

if TYPE_CHECKING:
    import aiohttp

    from hoyo_buddy.embeds import ErrorEmbed

    from ...bot.bot import HoyoBuddy

LOGGER_ = logging.getLogger(__name__)
CODE_NUM_TO_SLEEP = 15
SLEEP_INTERVAL = 60 * 5


class AutoRedeem:
    _bot: ClassVar["HoyoBuddy"]
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _redeem_count: ClassVar[int] = 0

    @classmethod
    async def _get_codes(cls, session: "aiohttp.ClientSession", game: genshin.Game) -> list[str]:
        async with session.get(f"https://hoyo-codes.vercel.app/codes?game={game.value}") as resp:
            return (await resp.json())["codes"]

    @classmethod
    async def _redeem_codes(cls, codes: list[str], account: HoyoAccount) -> None:
        # filter out codes that have already been redeemed
        codes = [code for code in codes if code not in account.redeemed_codes]
        if not codes:
            return

        await account.fetch_related("user", "user__settings")
        locale = account.user.settings.locale or Locale.american_english

        try:
            embed = await account.client.redeem_codes(
                codes, locale=locale, translator=cls._bot.translator, inline=True, blur=False
            )
            embed.set_footer(
                text=LocaleStr(
                    "Turn off auto code redemption with /redeem", key="auto_redeem_footer"
                )
            )
        except Exception as e:
            embed = await cls._handle_error(account, locale, e)
        else:
            account.redeemed_codes.extend(codes)
            # remove duplicates
            account.redeemed_codes = list(set(account.redeemed_codes))
            await account.save(update_fields=("redeemed_codes",))

            await cls._bot.dm_user(account.user.id, embed=embed)

            cls._redeem_count += len(embed.fields)
            if cls._redeem_count % CODE_NUM_TO_SLEEP == 0:
                # Sleep every n codes to prevent being rate limited
                await asyncio.sleep(SLEEP_INTERVAL)

    @classmethod
    async def _handle_error(
        cls, account: HoyoAccount, locale: Locale, e: Exception
    ) -> "ErrorEmbed":
        embed, recognized = get_error_embed(e, locale, cls._bot.translator)
        embed.add_acc_info(account, blur=False)
        if not recognized:
            cls._bot.capture_exception(e)

        content = LocaleStr(
            "An error occurred while performing automatic code redemption.\n"
            "Hoyo Buddy has disabled this feature for this account, you can turn it back on using </redeem>\n"
            "If this error persists or you don't know how to fix it, please contact the developer via </feedback>.\n",
            key="auto_redeem_error.content",
        )
        await cls._bot.dm_user(
            account.user.id,
            embed=embed,
            content=content.translate(cls._bot.translator, locale),
        )

        account.auto_redeem = False
        await account.save(update_fields=("auto_redeem",))

        return embed

    @classmethod
    async def execute(cls, bot: "HoyoBuddy") -> None:
        if cls._lock.locked():
            return

        async with cls._lock:
            LOGGER_.info("Starting auto redeem task")
            cls._bot = bot

            genshin_codes = await cls._get_codes(bot.session, genshin.Game.GENSHIN)
            hsr_codes = await cls._get_codes(bot.session, genshin.Game.STARRAIL)

            accounts = await HoyoAccount.filter(auto_redeem=True)
            for account in accounts:
                if account.game is Game.GENSHIN:
                    codes = genshin_codes
                elif account.game is Game.STARRAIL:
                    codes = hsr_codes
                else:
                    continue

                await cls._redeem_codes(codes, account)

            LOGGER_.info("Auto redeem task completed")
