from __future__ import annotations

import asyncio
import itertools
import os
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar, Literal

import discord
import genshin
from loguru import logger

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import GPY_GAME_TO_HB_GAME, PROXY_APIS
from hoyo_buddy.db.models import AccountNotifSettings, HoyoAccount, User
from hoyo_buddy.embeds import DefaultEmbed, Embed, ErrorEmbed

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.types import ProxyAPI

API_TOKEN = os.environ["DAILY_CHECKIN_API_TOKEN"]
MAX_API_ERROR_COUNT = 10
CHECKIN_SLEEP_TIME = 2.5
DM_SLEEP_TIME = 1.5


class DailyCheckin:
    _total_checkin_count: ClassVar[int]
    _bot: ClassVar[HoyoBuddy]
    _no_error_notify: ClassVar[bool]
    _embeds: ClassVar[defaultdict[int, list[tuple[int, Embed]]]]  # User ID -> (Account ID, Embed)

    @classmethod
    async def execute(
        cls, bot: HoyoBuddy, *, game: genshin.Game | None = None, no_error_notify: bool = False
    ) -> None:
        try:
            logger.info("Daily check-in started")

            cls._total_checkin_count = 0
            cls._bot = bot
            cls._no_error_notify = no_error_notify
            cls._embeds = defaultdict(list)

            queue: asyncio.Queue[HoyoAccount] = asyncio.Queue()
            the_rest: list[HoyoAccount] = []
            if game is None:
                accounts = await HoyoAccount.filter(daily_checkin=True).all()
            else:
                accounts = await HoyoAccount.filter(
                    daily_checkin=True, game=GPY_GAME_TO_HB_GAME[game]
                )

            for account in accounts:
                if account.region is genshin.Region.OVERSEAS:
                    await queue.put(account)
                else:
                    # Region is None or CN
                    the_rest.append(account)

            tasks = [asyncio.create_task(cls._daily_checkin_task(queue, api)) for api in PROXY_APIS]
            tasks.append(asyncio.create_task(cls._daily_checkin_task(queue, "LOCAL")))

            await queue.join()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

            # Claim for the rest of the accounts
            for account in the_rest:
                try:
                    embed = await cls._daily_checkin("LOCAL", account)
                except Exception as e:
                    logger.warning(f"Daily check-in failed for {account}")
                    cls._bot.capture_exception(e)
                else:
                    cls._total_checkin_count += 1
                    cls._embeds[account.user.id].append((account.id, embed))
                finally:
                    await asyncio.sleep(CHECKIN_SLEEP_TIME)

            # Send embeds
            for user_id, tuple_list in cls._embeds.items():
                await cls._notify_checkin_result(user_id, tuple_list)

        except Exception as e:
            bot.capture_exception(e)
        finally:
            logger.info(
                f"Daily check-in finished, total check-in count: {cls._total_checkin_count}"
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
                embed = await cls._daily_checkin(api_name, account)
            except Exception as e:
                await queue.put(account)
                api_error_count += 1

                logger.warning(f"Daily check-in failed for {account}")
                cls._bot.capture_exception(e)
                if api_error_count >= MAX_API_ERROR_COUNT:
                    msg = f"Daily check-in API {api_name} failed for {api_error_count} accounts"
                    raise RuntimeError(msg) from None
            else:
                cls._total_checkin_count += 1
                cls._embeds[account.user.id].append((account.id, embed))
            finally:
                await asyncio.sleep(CHECKIN_SLEEP_TIME)
                queue.task_done()

    @classmethod
    async def _notify_checkin_result(
        cls, user_id: int, tuple_list: list[tuple[int, Embed]]
    ) -> None:
        try:
            notif_settings: dict[int, AccountNotifSettings] = {}
            embeds: dict[int, Embed] = {}

            for tuple_ in tuple_list:
                account_id, embed = tuple_
                notif_setting = await AccountNotifSettings.get_or_none(account_id=account_id)
                if notif_setting is None:
                    notif_setting = await AccountNotifSettings.create(account_id=account_id)

                notif_settings[account_id] = notif_setting
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
                    if (
                        type_ == "error"
                        and account_id in notify_on_failure_ids
                        and not cls._no_error_notify
                    ) or (type_ == "success" and account_id in notify_on_success_ids):
                        embeds_to_send.append(embed)

                chunked_embeds = itertools.batched(embeds_to_send, 10)
                for chunk in chunked_embeds:
                    await cls._bot.dm_user(user_id, embeds=chunk)
                    await asyncio.sleep(DM_SLEEP_TIME)

        except Exception as e:
            cls._bot.capture_exception(e)

    @classmethod
    async def _daily_checkin(
        cls, api_name: ProxyAPI | Literal["LOCAL"], account: HoyoAccount
    ) -> Embed:
        await account.fetch_related("user", "user__settings")
        locale = account.user.settings.locale or discord.Locale.american_english
        client = account.client
        client.set_lang(locale)

        try:
            await client.update_cookies_for_checkin()
        except Exception as e:
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                cls._bot.capture_exception(e)

            embed.add_acc_info(account, blur=False)
            return embed

        try:
            reward = await client.claim_daily_reward(
                api_url=api_name if api_name == "LOCAL" else PROXY_APIS[api_name]
            )
        except Exception as e:
            if isinstance(e, genshin.DailyGeetestTriggered):
                await User.filter(id=account.user.id).update(
                    temp_data={"geetest": e.gt, "challenge": e.challenge}
                )
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                cls._bot.capture_exception(e)

            embed.add_acc_info(account, blur=False)
        else:
            embed = client.get_daily_reward_embed(reward, locale, blur=False)
        return embed
