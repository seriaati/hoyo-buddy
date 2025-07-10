from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar

import aiohttp
import genshin
from loguru import logger

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import CONCURRENT_TASK_NUM, HB_GAME_TO_GPY_GAME, MAX_PROXY_ERROR_NUM
from hoyo_buddy.db.models import DiscordEmbed
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.hoyo.auto_tasks.mixin import AutoTaskMixin
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import capture_exception, error_handler, get_now

if TYPE_CHECKING:
    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.embeds import DefaultEmbed, ErrorEmbed


SUPPORT_GAMES = (Game.GENSHIN, Game.STARRAIL, Game.ZZZ)


class AutoRedeem(AutoTaskMixin):
    _count: ClassVar[int]
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _error_counts: ClassVar[defaultdict[int, int]]

    @classmethod
    async def execute(cls, *, skip_redeemed: bool = True) -> None:
        """Redeem codes for accounts that have auto redeem enabled."""
        if cls._lock.locked():
            logger.debug(f"{cls.__name__} is already running")
            return

        async with cls._lock:
            start = asyncio.get_event_loop().time()

            try:
                cls._count = 0
                cls._error_counts = defaultdict(int)

                game_codes = await cls.get_codes()
                logger.debug(f"Game codes: {game_codes}")

                queue = await cls.build_auto_task_queue(
                    "redeem", games=SUPPORT_GAMES, region=genshin.Region.OVERSEAS
                )
                if queue.empty():
                    logger.debug(f"Queue is empty for {cls.__name__}")
                    return

                logger.info(f"Starting {cls.__name__} for {queue.qsize()} accounts")
                tasks = [
                    asyncio.create_task(
                        cls._redeem_code_task(queue, game_codes, skip_redeemed=skip_redeemed)
                    )
                    for _ in range(CONCURRENT_TASK_NUM)
                ]

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                capture_exception(e)
            else:
                logger.info(f"{cls.__name__} completed, count={cls._count}")
                logger.info(f"{cls.__name__} took {asyncio.get_event_loop().time() - start:.2f}s")

    @staticmethod
    async def get_codes() -> dict[Game, list[str]]:
        result: dict[Game, list[str]] = defaultdict(list)

        async with aiohttp.ClientSession() as session:
            for game in SUPPORT_GAMES:
                async with session.get(
                    f"https://hoyo-codes.seria.moe/codes?game={HB_GAME_TO_GPY_GAME[game].value}"
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to fetch codes for {game}, status={resp.status}")
                        continue

                    data = await resp.json()
                    result[game].extend(code["code"] for code in data["codes"])

        return result

    @classmethod
    async def _redeem_code_task(
        cls,
        queue: asyncio.Queue[HoyoAccount],
        game_codes: dict[Game, list[str]],
        *,
        skip_redeemed: bool,
    ) -> None:
        while True:
            account = await queue.get()
            logger.debug(f"{cls.__name__} is processing account {account}")
            codes = game_codes.get(account.game, [])
            if not codes:
                logger.debug(f"No codes for {account}, game={account.game}, marking task as done")
                queue.task_done()
                continue

            try:
                await account.fetch_related("user", "user__settings")
                embed = await cls._redeem_codes(account, codes, skip_redeemed=skip_redeemed)
            except Exception as e:
                with error_handler():
                    if cls._error_counts[account.id] >= MAX_PROXY_ERROR_NUM:
                        locale = account.user.settings.locale or Locale.american_english
                        embed, _ = get_error_embed(e, locale)
                        embed.add_acc_info(account, blur=False)
                        await DiscordEmbed.create(
                            embed,
                            user_id=account.user.id,
                            account_id=account.id,
                            task_type="redeem",
                        )
                    else:
                        cls._error_counts[account.id] += 1
                        capture_exception(e)
                        await queue.put(account)
            else:
                logger.debug(f"Setting last time for {account}, now={get_now()}")
                account.last_redeem_time = get_now()
                await account.save(update_fields=("last_redeem_time",))

                if embed is not None:
                    cls._count += 1
                    await DiscordEmbed.create(
                        embed, user_id=account.user.id, account_id=account.id, task_type="redeem"
                    )
            finally:
                queue.task_done()

    @classmethod
    async def _redeem_codes(
        cls, account: HoyoAccount, codes: list[str], *, skip_redeemed: bool
    ) -> DefaultEmbed | ErrorEmbed | None:
        locale = account.user.settings.locale or Locale.american_english

        try:
            client = account.client
            client.use_proxy = True
            client.set_lang(locale)

            embed = await account.client.redeem_codes(
                codes, locale=locale, blur=False, skip_redeemed=skip_redeemed
            )
            if embed is None:
                return None

            embed.set_footer(text=LocaleStr(key="auto_redeem_footer"))
        except Exception as e:
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                raise
            embed.add_acc_info(account, blur=False)
            return embed
        else:
            return embed
