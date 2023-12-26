import asyncio
import contextlib
import logging
import os
from typing import TYPE_CHECKING

import discord
import genshin

from ..bot.error_handler import get_error_embed
from ..bot.translator import LocaleStr, Translator
from ..db.enums import GAME_THUMBNAILS
from ..db.models import HoyoAccount, User
from ..embeds import DefaultEmbed, Embed, ErrorEmbed

if TYPE_CHECKING:
    import aiohttp

    from ..bot import HoyoBuddy

log = logging.getLogger(__name__)

CHECKIN_APIS = (
    "https://daily-checkin-api.vercel.app/",
    "https://dailycheckin-1-e3972598.deta.app/",
    "https://daily-checkin-api.onrender.com/",
)
API_TOKEN = os.environ["DAILY_CHECKIN_API_TOKEN"]
MAX_API_ERROR_COUNT = 10


class DailyCheckin:
    @classmethod
    async def execute(cls, bot: "HoyoBuddy") -> None:
        try:
            log.info("Daily check-in started")

            queue: asyncio.Queue[HoyoAccount] = asyncio.Queue()
            accounts = await HoyoAccount.filter(daily_checkin=True).prefetch_related(
                "user", "notif_settings"
            )
            for account in accounts:
                await queue.put(account)

            tasks = [
                asyncio.create_task(cls._daily_checkin_task(queue, api, bot))
                for api in CHECKIN_APIS
            ]
            tasks.append(asyncio.create_task(cls._daily_checkin_task(queue, "LOCAL", bot)))

            await queue.join()
            for task in tasks:
                task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:  # skipcq: PYL-W0703
            bot.capture_exception(e)

    @classmethod
    async def _daily_checkin_task(
        cls, queue: asyncio.Queue[HoyoAccount], api: str, bot: "HoyoBuddy"
    ) -> None:
        log.info("Daily check-in task started for %s", api)
        if api != "LOCAL":
            # test if the api is working
            async with bot.session.get(api) as resp:
                if resp.status != 200:
                    msg = f"API {api} returned {resp.status}"
                    raise RuntimeError(msg)

        api_error_count = 0

        while True:
            account = await queue.get()
            try:
                embed = await cls._daily_checkin(api, account, bot.translator, bot.session)
            except Exception:  # skipcq: PYL-W0703
                await queue.put(account)
                api_error_count += 1
                log.exception("Daily check-in failed for %s", account)
                if api_error_count >= MAX_API_ERROR_COUNT:
                    msg = f"Daily check-in API {api} failed for {api_error_count} accounts"
                    raise RuntimeError(msg) from None
            else:
                if (
                    isinstance(embed, ErrorEmbed)
                    and account.notif_settings.notify_on_checkin_failure
                ) or (
                    not isinstance(embed, DefaultEmbed)
                    and account.notif_settings.notify_on_checkin_success
                ):
                    await cls._notify_user(bot, account.user, embed)
            finally:
                await asyncio.sleep(2.0)
                queue.task_done()

    @classmethod
    async def _daily_checkin(
        cls,
        api: str,
        account: HoyoAccount,
        translator: Translator,
        session: "aiohttp.ClientSession",
    ) -> Embed:
        await account.fetch_related("user")
        await account.user.fetch_related("settings")

        locale = account.user.settings.locale or discord.Locale.american_english
        client = account.client
        client.set_lang(locale)
        if client.game is None:
            msg = "Client game is None"
            raise AssertionError(msg)

        if api == "LOCAL":
            try:
                reward = await account.client.claim_daily_reward()
            except Exception as e:  # skipcq: PYL-W0703
                embed, _ = get_error_embed(e, locale, translator)
                embed.set_author(
                    name=LocaleStr(account.game.value, warn_no_key=False),
                    icon_url=GAME_THUMBNAILS[account.game],
                )
            else:
                embed = client.get_daily_reward_embed(reward, client.game, locale, translator)
            return embed

        payload = {
            "token": API_TOKEN,
            "cookies": account.cookies,
            "lang": client.lang,
            "game": client.game.value,
        }
        async with session.post(f"{api}checkin/", json=payload) as resp:
            data = await resp.json()
            if resp.status == 200:
                reward = genshin.models.DailyReward(**data["data"])
                embed = client.get_daily_reward_embed(reward, client.game, locale, translator)
            elif resp.status == 400:
                try:
                    genshin.raise_for_retcode(data)
                except genshin.GenshinException as e:
                    embed, _ = get_error_embed(e, locale, translator)
                    embed.set_author(
                        name=LocaleStr(account.game.value, warn_no_key=False),
                        icon_url=GAME_THUMBNAILS[account.game],
                    )
            else:
                msg = f"API {api} returned {resp.status}"
                raise RuntimeError(msg)
        return embed

    @classmethod
    async def _notify_user(cls, bot: "HoyoBuddy", user: User, embed: Embed) -> None:
        with contextlib.suppress(discord.HTTPException):
            discord_user = await bot.get_or_fetch_user(user.id)
            if discord_user:
                await discord_user.send(embed=embed)
