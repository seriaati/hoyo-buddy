from __future__ import annotations

import asyncio
import itertools
import os
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar, Literal

import aiohttp
import discord
import genshin
from loguru import logger
from tortoise.queryset import Q

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import GPY_GAME_TO_HB_GAME, PROXY_APIS
from hoyo_buddy.db.models import AccountNotifSettings, HoyoAccount, User
from hoyo_buddy.embeds import DefaultEmbed, Embed, ErrorEmbed
from hoyo_buddy.enums import Game, Platform
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.types import ProxyAPI

API_TOKEN = os.environ["DAILY_CHECKIN_API_TOKEN"]
MAX_API_ERROR_COUNT = 10
MAX_API_RETRIES = 3
RETRY_SLEEP_TIME = 5
CHECKIN_SLEEP_TIME = 2.5
DM_SLEEP_TIME = 1.5


class DailyCheckin:
    _total_mimo_task_count: ClassVar[int]
    _bot: ClassVar[HoyoBuddy]
    _embeds: ClassVar[defaultdict[int, list[tuple[int, Embed]]]]  # User ID -> (Account ID, Embed)

    @classmethod
    async def execute(cls, bot: HoyoBuddy) -> None:
        try:
            logger.info("Auto mimo task started")

            cls._total_mimo_task_count = 0
            cls._bot = bot
            cls._embeds = defaultdict(list)

            queue: asyncio.Queue[HoyoAccount] = asyncio.Queue()
            accounts = await HoyoAccount.filter(
                Q(game=Game.STARRAIL) | Q(game=Game.ZZZ), mimo_auto_task=True
            )

            for account in accounts:
                if account.platform is Platform.MIYOUSHE:
                    continue
                await queue.put(account)

            tasks = [asyncio.create_task(cls._daily_checkin_task(queue, api)) for api in PROXY_APIS]
            tasks.append(asyncio.create_task(cls._daily_checkin_task(queue, "LOCAL")))

            await queue.join()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

            # Send embeds
            for user_id, tuple_list in cls._embeds.items():
                await cls._notify_checkin_result(user_id, tuple_list)

        except Exception as e:
            bot.capture_exception(e)
        finally:
            logger.info(
                f"Daily check-in finished, total check-in count: {cls._total_mimo_task_count}"
            )

    @classmethod
    async def _daily_checkin_task(
        cls, queue: asyncio.Queue[HoyoAccount], api_name: ProxyAPI | Literal["LOCAL"]
    ) -> None:
        logger.info(f"Daily check-in task started for api: {api_name}")

        bot = cls._bot
        if api_name != "LOCAL":
            # test if the api is working
            async with bot.session.get(PROXY_APIS[api_name]) as resp:
                if resp.status != 200:
                    msg = f"API {api_name} returned {resp.status}"
                    raise RuntimeError(msg)

        api_error_count = 0

        while True:
            account = await queue.get()

            try:
                embed = await cls._complete_mimo_tasks(api_name, account)
            except Exception as e:
                await queue.put(account)
                api_error_count += 1

                logger.warning(f"Daily check-in failed for {account}")
                cls._bot.capture_exception(e)
                if api_error_count >= MAX_API_ERROR_COUNT:
                    msg = f"Daily check-in API {api_name} failed for {api_error_count} accounts"
                    raise RuntimeError(msg) from None
            else:
                cls._total_mimo_task_count += 1
                cls._embeds[account.user.id].append((account.id, embed))
            finally:
                await asyncio.sleep(CHECKIN_SLEEP_TIME)
                queue.task_done()

    @classmethod
    async def _notify_checkin_result(
        cls, user_id: int, tuple_list: list[tuple[int, Embed]]
    ) -> None:
        try:
            embeds: dict[int, Embed] = {}

            for tuple_ in tuple_list:
                account_id, embed = tuple_
                embeds[account_id] = embed

            typed_embeds: defaultdict[Literal["error", "success"], list[tuple[int, Embed]]] = (
                defaultdict(list)
            )
            for account_id, embed in embeds.items():
                if isinstance(embed, ErrorEmbed):
                    typed_embeds["error"].append((account_id, embed))
                elif isinstance(embed, DefaultEmbed):
                    typed_embeds["success"].append((account_id, embed))

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

            for type_, embed_tuples in typed_embeds.items():
                embeds_to_send: list[Embed] = []
                for account_id, embed in embed_tuples:
                    if (type_ == "error" and account_id in notify_on_failure_ids) or (
                        type_ == "success" and account_id in notify_on_success_ids
                    ):
                        embeds_to_send.append(embed)

                chunked_embeds = itertools.batched(embeds_to_send, 10)
                for chunk in chunked_embeds:
                    await cls._bot.dm_user(user_id, embeds=chunk)
                    await asyncio.sleep(DM_SLEEP_TIME)

        except Exception as e:
            cls._bot.capture_exception(e)

    @classmethod
    async def _complete_mimo_tasks(
        cls, api_name: ProxyAPI | Literal["LOCAL"], account: HoyoAccount
    ) -> Embed | None:
        session = cls._bot.session
        await account.fetch_related("user", "user__settings")
        locale = account.user.settings.locale or discord.Locale.american_english
        client = account.client
        client.set_lang(locale)

        finish_count, claim_point = await client.finish_and_claim_mimo_tasks(
            session, api_url=api_name if api_name == "LOCAL" else PROXY_APIS[api_name]
        )
        if finish_count == 0 and claim_point == 0:
            return None

        embed = DefaultEmbed(
            locale,
            title=LocaleStr(
                custom_str="{mimo_title} {label}",
                mimo_title=LocaleStr(key="point_detail_tag_mimo", mi18n_game="mimo"),
                label=LocaleStr(key="mimo_auto_finish_and_claim_button_label"),
            ),
            description=LocaleStr(
                key="mimo_auto_task_embed_desc", finish=finish_count, claim=claim_point
            ),
        )
        embed.set_footer(text=LocaleStr(key="mimo_auto_task_embed_footer"))
        return embed
