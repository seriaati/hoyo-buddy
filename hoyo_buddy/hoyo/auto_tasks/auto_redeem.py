from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar

import genshin
from discord import Locale
from loguru import logger

from ...bot.error_handler import get_error_embed
from ...bot.translator import LocaleStr
from ...constants import HB_GAME_TO_GPY_GAME
from ...db.models import HoyoAccount
from ...enums import Game, Platform

if TYPE_CHECKING:
    import aiohttp

    from hoyo_buddy.embeds import ErrorEmbed

    from ...bot import HoyoBuddy

CODE_NUM_TO_SLEEP = 15
SLEEP_INTERVAL = 60 * 5


class AutoRedeem:
    _bot: ClassVar[HoyoBuddy]
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _redeem_count: ClassVar[int] = 0

    @classmethod
    async def _get_codes(cls, session: aiohttp.ClientSession, game: genshin.Game) -> list[str]:
        async with session.get(f"https://hoyo-codes.seriaati.xyz/codes?game={game.value}") as resp:
            data = await resp.json()
            return [code["code"] for code in data["codes"]]

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
            embed.set_footer(text=LocaleStr(key="auto_redeem_footer"))
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
    async def _handle_error(cls, account: HoyoAccount, locale: Locale, e: Exception) -> ErrorEmbed:
        embed, recognized = get_error_embed(e, locale, cls._bot.translator)
        embed.add_acc_info(account, blur=False)
        if not recognized:
            cls._bot.capture_exception(e)

        content = LocaleStr(key="auto_redeem_error.content")
        await cls._bot.dm_user(
            account.user.id,
            embed=embed,
            content=content.translate(cls._bot.translator, locale),
        )

        account.auto_redeem = False
        await account.save(update_fields=("auto_redeem",))

        return embed

    @classmethod
    async def execute(
        cls, bot: HoyoBuddy, game: genshin.Game | None = None, codes: list[str] | None = None
    ) -> bool:
        """Redeem codes for accounts that have auto redeem enabled.

        Args:
            bot: The bot instance.
            game: The game to redeem codes for, all games if None.
            codes: The codes to redeem, None to fetch from API.

        Returns:
            True if the task was successful, False if the task was already running.
        """
        if cls._lock.locked():
            return False

        async with cls._lock:
            logger.info(
                f"Starting auto redeem task for game {game or 'all'} and codes {codes or 'from API'}"
            )
            cls._bot = bot

            game_codes = (
                {game: codes}
                if game is not None and codes is not None
                else {
                    game_: await cls._get_codes(bot.session, game_)
                    for game_ in (genshin.Game.GENSHIN, genshin.Game.ZZZ, genshin.Game.STARRAIL)
                }
            )

            accounts = (
                await HoyoAccount.filter(auto_redeem=True, game=game).all()
                if game is not None
                else await HoyoAccount.filter(auto_redeem=True).all()
            )

            for account in accounts:
                if account.platform is Platform.MIYOUSHE or account.game is Game.HONKAI:
                    continue

                await cls._redeem_codes(
                    game_codes.get(HB_GAME_TO_GPY_GAME[account.game], []), account
                )

            logger.info("Auto redeem task completed")

        return True
