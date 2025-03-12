from __future__ import annotations

import asyncio
import itertools
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar

import discord
import genshin
from loguru import logger

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import sleep
from hoyo_buddy.db import AccountNotifSettings, HoyoAccount, User
from hoyo_buddy.embeds import DefaultEmbed, Embed, ErrorEmbed
from hoyo_buddy.utils import get_now

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.enums import Game


class DailyCheckin:
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _count: ClassVar[int]
    _bot: ClassVar[HoyoBuddy]
    _no_error_notify: ClassVar[bool]

    _embeds: ClassVar[defaultdict[int, list[tuple[int, Embed]]]]
    """User ID -> (Account ID, Embed)"""

    @classmethod
    async def execute(
        cls, bot: HoyoBuddy, *, game: Game | None = None, no_error_notify: bool = False
    ) -> None:
        if cls._lock.locked():
            logger.debug(f"{cls.__name__} is already running")
            return

        async with cls._lock:
            start = asyncio.get_event_loop().time()

            try:
                logger.info("Daily check-in started")

                cls._count = 0
                cls._bot = bot

                cls._no_error_notify = no_error_notify
                cls._embeds = defaultdict(list)

                queue = await cls._bot.build_auto_task_queue(
                    "checkin", games=[game] if game else None
                )
                if queue.empty():
                    logger.debug(f"Queue is empty for {cls.__name__}, {game=}")
                    return

                logger.info(f"Starting {cls.__name__} for {queue.qsize()} accounts")
                tasks = [asyncio.create_task(cls._daily_checkin_task(queue)) for _ in range(100)]

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

                # Send embeds
                for user_id, embeds in cls._embeds.items():
                    await cls._notify_checkin_result(user_id, embeds)
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
                await queue.put(account)
                cls._bot.capture_exception(e)
            else:
                cls._count += 1
                cls._embeds[account.user.id].append((account.id, embed))

                logger.debug(f"Setting last time for {account}, now={get_now()}")
                account.last_checkin_time = get_now()
                await account.save(update_fields=("last_checkin_time",))
            finally:
                await sleep("checkin")
                queue.task_done()

    @classmethod
    async def _notify_checkin_result(cls, user_id: int, embeds: list[tuple[int, Embed]]) -> None:
        try:
            notif_settings: dict[int, AccountNotifSettings] = {}

            for account_id, _ in embeds:
                notif_setting = await AccountNotifSettings.get_or_none(account_id=account_id)
                if notif_setting is None:
                    notif_setting = await AccountNotifSettings.create(account_id=account_id)

                notif_settings[account_id] = notif_setting

            notify_on_failure_ids = {
                account_id
                for account_id, notif_setting in notif_settings.items()
                if notif_setting.notify_on_checkin_failure
            }
            notify_on_success_ids = {
                account_id
                for account_id, notif_setting in notif_settings.items()
                if notif_setting.notify_on_checkin_success
            }

            embeds_to_send: list[Embed] = []

            for account_id, embed in embeds:
                if (
                    isinstance(embed, ErrorEmbed)
                    and account_id in notify_on_failure_ids
                    and not cls._no_error_notify
                ) or (isinstance(embed, DefaultEmbed) and account_id in notify_on_success_ids):
                    embeds_to_send.append(embed)

            chunked_embeds = itertools.batched(embeds_to_send, 10)
            for chunk in chunked_embeds:
                await cls._bot.dm_user(user_id, embeds=chunk)
                await sleep("dm")

        except Exception as e:
            cls._bot.capture_exception(e)

    @classmethod
    async def _daily_checkin(cls, account: HoyoAccount) -> DefaultEmbed | ErrorEmbed:
        locale = account.user.settings.locale or discord.Locale.american_english

        try:
            client = account.client
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
