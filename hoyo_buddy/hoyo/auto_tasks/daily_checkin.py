from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar

import discord
import genshin
from loguru import logger

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import CONCURRENT_TASK_NUM, MAX_PROXY_ERROR_NUM
from hoyo_buddy.db import HoyoAccount, User
from hoyo_buddy.db.models import DiscordEmbed
from hoyo_buddy.utils import error_handler, get_now, sleep

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.embeds import DefaultEmbed, ErrorEmbed
    from hoyo_buddy.enums import Game


class DailyCheckin:
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _count: ClassVar[int]
    _bot: ClassVar[HoyoBuddy]
    _error_counts: ClassVar[defaultdict[int, int]]

    @classmethod
    async def execute(cls, bot: HoyoBuddy, *, game: Game | None = None) -> None:
        if cls._lock.locked():
            logger.debug(f"{cls.__name__} is already running")
            return

        async with cls._lock:
            start = asyncio.get_event_loop().time()

            try:
                cls._count = 0
                cls._bot = bot
                cls._error_counts = defaultdict(int)

                queue = await cls._bot.build_auto_task_queue(
                    "checkin", games=[game] if game else None
                )
                if queue.empty():
                    logger.debug(f"Queue is empty for {cls.__name__}, {game=}")
                    return

                logger.info(f"Starting {cls.__name__} for {queue.qsize()} accounts")
                tasks = [
                    asyncio.create_task(cls._daily_checkin_task(queue))
                    for _ in range(CONCURRENT_TASK_NUM)
                ]

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                bot.capture_exception(e)
            else:
                logger.info(f"{cls.__name__} finished, count={cls._count}")
                logger.info(
                    f"{cls.__name__} took {asyncio.get_event_loop().time() - start:.2f} seconds"
                )

    @classmethod
    async def _daily_checkin_task(cls, queue: asyncio.Queue[HoyoAccount]) -> None:
        while True:
            account = await queue.get()
            logger.debug(f"{cls.__name__} is processing account {account}")

            try:
                await account.fetch_related("user", "user__settings")
                embed = await cls._daily_checkin(account)
            except Exception as e:
                with error_handler():
                    if cls._error_counts[account.id] >= MAX_PROXY_ERROR_NUM:
                        locale = account.user.settings.locale or discord.Locale.american_english
                        embed, _ = get_error_embed(e, locale)
                        embed.add_acc_info(account, blur=False)
                        await DiscordEmbed.create(
                            embed,
                            user_id=account.user.id,
                            account_id=account.id,
                            task_type="checkin",
                        )
                    else:
                        cls._error_counts[account.id] += 1
                        cls._bot.capture_exception(e)
                        await queue.put(account)
            else:
                cls._count += 1
                await DiscordEmbed.create(
                    embed, user_id=account.user.id, account_id=account.id, task_type="checkin"
                )

                logger.debug(f"Setting last time for {account}, now={get_now()}")
                account.last_checkin_time = get_now()
                await account.save(update_fields=("last_checkin_time",))
            finally:
                await sleep("checkin")
                queue.task_done()

    @classmethod
    async def _daily_checkin(cls, account: HoyoAccount) -> DefaultEmbed | ErrorEmbed:
        locale = account.user.settings.locale or discord.Locale.american_english

        try:
            client = account.client
            client.use_proxy = True
            client.set_lang(locale)

            await client.update_cookies_for_checkin()
            reward = await client.claim_daily_reward()
            embed = client.get_daily_reward_embed(reward, locale, blur=False)
        except Exception as e:
            if isinstance(e, genshin.DailyGeetestTriggered):
                await User.filter(id=account.user.id).update(
                    temp_data={"geetest": e.gt, "challenge": e.challenge}
                )

            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                raise
            embed.add_acc_info(account, blur=False)
            return embed
        else:
            return embed
