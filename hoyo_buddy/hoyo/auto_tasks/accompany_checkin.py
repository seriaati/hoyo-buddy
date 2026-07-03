from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar

import genshin
from loguru import logger

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import ACCOMPANY_SUPPORT_GAMES, CONCURRENT_TASK_NUM, MAX_PROXY_ERROR_NUM
from hoyo_buddy.db.models import DiscordEmbed
from hoyo_buddy.enums import Locale
from hoyo_buddy.hoyo.auto_tasks.mixin import AutoTaskMixin
from hoyo_buddy.utils import capture_exception, error_handler, get_now, sleep

if TYPE_CHECKING:
    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.embeds import DefaultEmbed, ErrorEmbed


class AccompanyCheckin(AutoTaskMixin):
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _count: ClassVar[int]
    _error_counts: ClassVar[defaultdict[int, int]]

    @classmethod
    async def execute(cls) -> None:
        if cls._lock.locked():
            logger.debug(f"{cls.__name__} is already running")
            return

        async with cls._lock:
            start = asyncio.get_event_loop().time()

            try:
                cls._count = 0
                cls._error_counts = defaultdict(int)

                queue = await cls.build_auto_task_queue(
                    "accompany", games=list(ACCOMPANY_SUPPORT_GAMES), region=genshin.Region.OVERSEAS
                )
                if queue.empty():
                    logger.debug(f"Queue is empty for {cls.__name__}")
                    return

                logger.info(f"Starting {cls.__name__} for {queue.qsize()} accounts")
                tasks = [
                    asyncio.create_task(cls._accompany_task(queue))
                    for _ in range(CONCURRENT_TASK_NUM)
                ]

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                capture_exception(e)
            else:
                logger.info(f"{cls.__name__} finished, count={cls._count}")
                logger.info(
                    f"{cls.__name__} took {asyncio.get_event_loop().time() - start:.2f} seconds"
                )

    @classmethod
    async def _accompany_task(cls, queue: asyncio.Queue[HoyoAccount]) -> None:
        while True:
            account = await queue.get()
            logger.debug(f"{cls.__name__} is processing account {account}")

            try:
                await account.fetch_related("user", "user__settings")
                embed = await cls._accompany(account)
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
                            task_type="accompany",
                        )
                    else:
                        cls._error_counts[account.id] += 1
                        capture_exception(e)
                        await queue.put(account)
            else:
                cls._count += 1
                if embed is not None:
                    await DiscordEmbed.create(
                        embed, user_id=account.user.id, account_id=account.id, task_type="accompany"
                    )

                account.last_accompany_time = get_now()
                await account.save(update_fields=("last_accompany_time",))
            finally:
                await sleep("accompany")
                queue.task_done()

    @classmethod
    async def _accompany(cls, account: HoyoAccount) -> DefaultEmbed | ErrorEmbed | None:
        locale = account.user.settings.locale or Locale.american_english

        try:
            client = account.client
            client.use_proxy = True
            client.set_lang(locale)

            details = await client.get_accompany_character_details(
                topic_id=account.accompany_topic_id  # pyright: ignore[reportArgumentType]
            )
            if details.accompany_info.accompanied_today:
                return None

            result = await client.accompany_character(
                role_id=account.accompany_role_id,  # pyright: ignore[reportArgumentType]
                topic_id=account.accompany_topic_id,  # pyright: ignore[reportArgumentType]
            )
            if result.points_increased == 0:
                return None

            embed = client.get_accompany_embed(result, details.info.name, locale)
        except Exception as e:
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                raise
            embed.add_acc_info(account, blur=False)
            return embed
        else:
            return embed
