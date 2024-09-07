from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, ClassVar, Literal

import discord
import genshin
from loguru import logger

from ...bot.error_handler import get_error_embed
from ...db.models import AccountNotifSettings, HoyoAccount, User
from ...embeds import DefaultEmbed, Embed, ErrorEmbed

if TYPE_CHECKING:
    import aiohttp

    from ...bot import HoyoBuddy
    from ...l10n import Translator


CHECKIN_APIS: dict[Literal["VERCEL", "DETA", "FLY"], str] = {
    "VERCEL": "https://daily-checkin-api.vercel.app",
    "DETA": "https://dailycheckin-1-e3972598.deta.app",
    "FLY": "https://daily-checkin-api.fly.dev/",
}
API_TOKEN = os.environ["DAILY_CHECKIN_API_TOKEN"]
MAX_API_ERROR_COUNT = 10


class DailyCheckin:
    _total_checkin_count: ClassVar[int]

    @classmethod
    async def execute(cls, bot: HoyoBuddy) -> None:
        try:
            logger.info("Daily check-in started")

            cls._total_checkin_count = 0
            cls._bot = bot

            queue: asyncio.Queue[HoyoAccount] = asyncio.Queue()
            accounts = await HoyoAccount.filter(daily_checkin=True).all()
            for account in accounts:
                await queue.put(account)

            tasks = [
                asyncio.create_task(cls._daily_checkin_task(queue, api)) for api in CHECKIN_APIS
            ]
            tasks.append(asyncio.create_task(cls._daily_checkin_task(queue, "LOCAL")))

            await queue.join()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            bot.capture_exception(e)
        finally:
            logger.info(
                "Daily check-in finished, total check-in count: %d", cls._total_checkin_count
            )

    @classmethod
    async def _daily_checkin_task(
        cls, queue: asyncio.Queue[HoyoAccount], api_name: Literal["VERCEL", "DETA", "FLY", "LOCAL"]
    ) -> None:
        logger.info(f"Daily check-in task started for api: {api_name}")

        bot = cls._bot
        if api_name != "LOCAL":
            # test if the api is working
            async with bot.session.get(CHECKIN_APIS[api_name]) as resp:
                if resp.status != 200:
                    msg = f"API {api_name} returned {resp.status}"
                    raise RuntimeError(msg)

        api_error_count = 0

        while True:
            account = await queue.get()
            try:
                await account.fetch_related("user")
                embed = await cls._daily_checkin(api_name, account, bot.translator, bot.session)
            except Exception:
                await queue.put(account)
                api_error_count += 1
                logger.exception(f"Daily check-in failed for {account}")
                if api_error_count >= MAX_API_ERROR_COUNT:
                    msg = f"Daily check-in API {api_name} failed for {api_error_count} accounts"
                    raise RuntimeError(msg) from None
            else:
                cls._total_checkin_count += 1
                try:
                    notif_settings, _ = await AccountNotifSettings.get_or_create(account=account)
                    if (
                        isinstance(embed, ErrorEmbed) and notif_settings.notify_on_checkin_failure
                    ) or (
                        isinstance(embed, DefaultEmbed) and notif_settings.notify_on_checkin_success
                    ):
                        await cls._bot.dm_user(account.user.id, embed=embed)
                except Exception as e:
                    cls._bot.capture_exception(e)
            finally:
                await asyncio.sleep(2.3)
                queue.task_done()

    @classmethod
    async def _daily_checkin(
        cls,
        api_name: Literal["VERCEL", "DETA", "FLY", "LOCAL"],
        account: HoyoAccount,
        translator: Translator,
        session: aiohttp.ClientSession,
    ) -> Embed:
        await account.user.fetch_related("settings")
        locale = account.user.settings.locale or discord.Locale.american_english
        client = account.client
        client.set_lang(locale)

        try:
            updated_cookies = await client.update_cookies_for_checkin()
        except Exception as e:
            embed, recognized = get_error_embed(e, locale, translator)
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
                embed, recognized = get_error_embed(e, locale, translator)
                if not recognized:
                    cls._bot.capture_exception(e)

                embed.add_acc_info(account, blur=False)
            else:
                embed = client.get_daily_reward_embed(reward, locale, translator, blur=False)
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
        api_url = CHECKIN_APIS[api_name]
        async with session.post(f"{api_url}/checkin/", json=payload) as resp:
            data = await resp.json()
            if resp.status == 200:
                reward = genshin.models.DailyReward(**data["data"])
                embed = client.get_daily_reward_embed(reward, locale, translator, blur=False)
            elif resp.status == 400:
                if data["retcode"] == -9999:
                    await User.filter(id=account.user.id).update(temp_data=data["data"])
                try:
                    genshin.raise_for_retcode(data)
                except genshin.GenshinException as e:
                    embed, recognized = get_error_embed(e, locale, translator)
                    if not recognized:
                        cls._bot.capture_exception(e)

                    embed.add_acc_info(account, blur=False)
            else:
                msg = f"API {api_name} returned {resp.status}"
                raise RuntimeError(msg)

        return embed
