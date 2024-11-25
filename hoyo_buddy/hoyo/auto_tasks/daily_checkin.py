from __future__ import annotations

import asyncio
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
MAX_API_RETRIES = 3
RETRY_SLEEP_TIME = 5
CHECKIN_SLEEP_TIME = 2.5


class DailyCheckin:
    _total_checkin_count: ClassVar[int]
    _bot: ClassVar[HoyoBuddy]
    _no_error_notify: ClassVar[bool]
    _embeds: ClassVar[defaultdict[int, list[Embed]]]  # Account ID -> embeds

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
                    cls._embeds[account.id].append(embed)
                finally:
                    await asyncio.sleep(CHECKIN_SLEEP_TIME)

            # Send embeds
            for account_id, embeds in cls._embeds.items():
                account = next((a for a in accounts if a.id == account_id), None)
                if account is None:
                    continue

                for embed in embeds:
                    await cls._notify_checkin_result(account, embed)
                    await asyncio.sleep(CHECKIN_SLEEP_TIME)

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
                cls._embeds[account.id].append(embed)
            finally:
                await asyncio.sleep(CHECKIN_SLEEP_TIME)
                queue.task_done()

    @classmethod
    async def _notify_checkin_result(cls, account: HoyoAccount, embed: Embed) -> None:
        try:
            notif_settings = await AccountNotifSettings.get_or_none(account=account)
            if notif_settings is None:
                notif_settings = await AccountNotifSettings.create(account=account)

            if (
                isinstance(embed, ErrorEmbed)
                and notif_settings.notify_on_checkin_failure
                and not cls._no_error_notify
            ) or (isinstance(embed, DefaultEmbed) and notif_settings.notify_on_checkin_success):
                await cls._bot.dm_user(account.user.id, embed=embed)
        except Exception as e:
            cls._bot.capture_exception(e)

    @classmethod
    async def _daily_checkin(
        cls, api_name: ProxyAPI | Literal["LOCAL"], account: HoyoAccount, *, retry: int = 0
    ) -> Embed:
        session = cls._bot.session
        await account.fetch_related("user", "user__settings")
        locale = account.user.settings.locale or discord.Locale.american_english
        client = account.client
        client.set_lang(locale)

        try:
            updated_cookies = await client.update_cookies_for_checkin()
        except Exception as e:
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                cls._bot.capture_exception(e)

            embed.add_acc_info(account, blur=False)
            return embed

        cookies = updated_cookies or account.cookies

        if api_name == "LOCAL":
            try:
                reward = await client.claim_daily_reward()
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

        # API check-in
        assert client.game is not None
        payload = {
            "token": API_TOKEN,
            "cookies": cookies,
            "lang": client.lang,
            "game": client.game.value,
            "region": client.region.value,
        }
        api_url = PROXY_APIS[api_name]

        logger_payload = payload.copy()
        logger_payload.pop("cookies")
        logger_payload.pop("token")
        logger.debug(f"Check-in payload: {logger_payload}")

        try:
            async with session.post(f"{api_url}/checkin/", json=payload) as resp:
                if resp.status == 502:
                    await asyncio.sleep(20)
                    embed = await cls._daily_checkin(api_name, account)
                elif resp.status in {200, 400, 500}:
                    data = await resp.json()
                    logger.debug(f"Check-in response: {data}")

                    if resp.status == 200:
                        # Correct reward amount
                        monthly_rewards = await client.get_monthly_rewards()
                        reward = next(
                            (r for r in monthly_rewards if r.icon == data["data"]["icon"]), None
                        )
                        if reward is None:
                            reward = genshin.models.DailyReward(**data["data"])
                        embed = client.get_daily_reward_embed(reward, locale, blur=False)
                    elif resp.status == 400:
                        if data["retcode"] == -9999:
                            await User.filter(id=account.user.id).update(temp_data=data["data"])

                        e = genshin.GenshinException(data)
                        embed, recognized = get_error_embed(e, locale)
                        if not recognized:
                            cls._bot.capture_exception(e)

                        embed.add_acc_info(account, blur=False)
                    else:  # 500
                        msg = f"API {api_name} errored: {data['message']}"
                        raise RuntimeError(msg)
                else:
                    msg = f"API {api_name} returned {resp.status}"
                    raise RuntimeError(msg)
        except Exception:
            if retry > MAX_API_RETRIES:
                raise
            await asyncio.sleep(RETRY_SLEEP_TIME)
            return await cls._daily_checkin(api_name, account, retry=retry + 1)

        return embed
