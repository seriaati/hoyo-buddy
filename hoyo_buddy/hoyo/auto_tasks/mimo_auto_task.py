from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, ClassVar, Literal

import discord
import genshin
from loguru import logger
from tortoise.expressions import Q

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import PROXY_APIS
from hoyo_buddy.db.models import HoyoAccount
from hoyo_buddy.embeds import DefaultEmbed, Embed, ErrorEmbed
from hoyo_buddy.enums import Game, Platform
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.types import ProxyAPI

API_TOKEN = os.environ["DAILY_CHECKIN_API_TOKEN"]
MAX_API_ERROR_COUNT = 10
SLEEP_TIME = 2.5


class MimoAutoTask:
    _total_count: ClassVar[int]
    _bot: ClassVar[HoyoBuddy]

    @classmethod
    async def execute(cls, bot: HoyoBuddy) -> None:
        try:
            logger.info("Auto mimo task started")

            cls._total_count = 0
            cls._bot = bot

            queue: asyncio.Queue[HoyoAccount] = asyncio.Queue()
            accounts = await HoyoAccount.filter(
                Q(game=Game.STARRAIL) | Q(game=Game.ZZZ), mimo_auto_task=True
            )

            for account in accounts:
                if account.platform is Platform.MIYOUSHE:
                    continue
                await queue.put(account)

            tasks = [asyncio.create_task(cls._mimo_task(queue, api)) for api in PROXY_APIS]
            tasks.append(asyncio.create_task(cls._mimo_task(queue, "LOCAL")))

            await queue.join()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            bot.capture_exception(e)
        finally:
            logger.info(f"Mimo auto task finished, total count: {cls._total_count}")

    @classmethod
    async def _mimo_task(
        cls, queue: asyncio.Queue[HoyoAccount], api_name: ProxyAPI | Literal["LOCAL"]
    ) -> None:
        logger.info(f"Mimo task started for api: {api_name}")

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

                logger.warning(f"Mimo auto task failed for {account}")
                cls._bot.capture_exception(e)
                if api_error_count >= MAX_API_ERROR_COUNT:
                    msg = f"Proxy API {api_name} failed for {api_error_count} accounts"
                    raise RuntimeError(msg) from None
            else:
                if embed is not None:
                    cls._total_count += 1
                    embed.set_footer(text=LocaleStr(key="mimo_auto_task_embed_footer"))
                    embed.add_acc_info(account)

                    if isinstance(embed, ErrorEmbed):
                        account.mimo_auto_task = False
                        await account.save(update_fields=("mimo_auto_task",))
                        content = LocaleStr(key="mimo_auto_task_error_dm_content").translate(
                            account.user.settings.locale or discord.Locale.american_english
                        )
                    else:
                        content = None

                    await cls._bot.dm_user(account.user.id, embed=embed, content=content)

            finally:
                await asyncio.sleep(SLEEP_TIME)
                queue.task_done()

    @classmethod
    async def _complete_mimo_tasks(
        cls, api_name: ProxyAPI | Literal["LOCAL"], account: HoyoAccount
    ) -> Embed | None:
        await account.fetch_related("user", "user__settings")
        locale = account.user.settings.locale or discord.Locale.american_english
        client = account.client
        client.set_lang(locale)

        try:
            finish_count, claim_point = await client.finish_and_claim_mimo_tasks(
                api_url=api_name if api_name == "LOCAL" else PROXY_APIS[api_name]
            )
        except genshin.GenshinException as e:
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                cls._bot.capture_exception(e)
            return embed

        if finish_count == 0 and claim_point == 0:
            return None

        return DefaultEmbed(
            locale,
            title=LocaleStr(
                custom_str="{mimo_title} {label}",
                mimo_title=LocaleStr(key="point_detail_tag_mimo", mi18n_game="mimo"),
                label=LocaleStr(key="mimo_auto_finish_and_claim_button_label"),
            ),
            description=LocaleStr(
                key="mimo_auto_task_embed_desc", finish=finish_count, claim_point=claim_point
            ),
        )
