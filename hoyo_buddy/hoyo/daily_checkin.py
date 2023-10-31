import asyncio
import logging
import os

import aiohttp
import discord
import genshin

from ..bot import HoyoBuddy
from ..bot.embeds import Embed
from ..bot.error_handler import get_error_embed
from ..bot.translator import Translator
from ..bot.translator import locale_str as _T
from ..db.enums import GAME_THUMBNAILS
from ..db.models import HoyoAccount, User

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
    async def exec(cls, bot: HoyoBuddy) -> None:
        try:
            log.info("Daily check-in started")

            queue: asyncio.Queue[HoyoAccount] = asyncio.Queue()
            accounts = await HoyoAccount.filter(daily_checkin=True).prefetch_related(
                "user"
            )
            for account in accounts:
                await queue.put(account)

            tasks = [
                asyncio.create_task(cls._daily_checkin_task(queue, api, bot))
                for api in CHECKIN_APIS
            ]
            tasks.append(
                asyncio.create_task(cls._daily_checkin_task(queue, "LOCAL", bot))
            )

            await queue.join()
            for task in tasks:
                task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:  # skipcq: PYL-W0703
            log.error("Daily check-in failed: %s", e)

    @classmethod
    async def _daily_checkin_task(
        cls, queue: asyncio.Queue[HoyoAccount], api: str, bot: HoyoBuddy
    ) -> None:
        log.info("Daily check-in task started for %s", api)
        if api != "LOCAL":
            # test if the api is working
            async with bot.session.get(api) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"API {api} returned {resp.status}")

        api_error_count = 0

        while True:
            account = await queue.get()
            try:
                embed = await cls._daily_checkin(
                    api, account, bot.translator, bot.session
                )
            except Exception as e:  # skipcq: PYL-W0703
                await queue.put(account)
                api_error_count += 1
                log.error("Daily check-in failed for %s", account, exc_info=e)
                if api_error_count >= MAX_API_ERROR_COUNT:
                    raise RuntimeError(
                        f"Daily check-in API {api} failed for {api_error_count} accounts"
                    )
            else:
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
        session: aiohttp.ClientSession,
    ) -> Embed:
        await account.fetch_related("user")
        await account.user.fetch_related("settings")

        locale = account.user.settings.locale or discord.Locale.american_english
        client = account.client
        client.set_lang(locale)
        if client.game is None:
            raise AssertionError("Client game is None")

        if api == "LOCAL":
            try:
                reward = await account.client.claim_daily_reward()
            except Exception as e:  # skipcq: PYL-W0703
                embed = get_error_embed(e, locale, translator)
                embed.set_author(
                    name=_T(account.game.value, warn_no_key=False),
                    icon_url=GAME_THUMBNAILS[account.game],
                )
            else:
                embed = client.get_daily_reward_embed(
                    reward, client.game, locale, translator
                )
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
                embed = client.get_daily_reward_embed(
                    reward, client.game, locale, translator
                )
            elif resp.status == 400:
                try:
                    genshin.raise_for_retcode(data)
                except genshin.GenshinException as e:
                    embed = get_error_embed(e, locale, translator)
                    embed.set_author(
                        name=_T(account.game.value, warn_no_key=False),
                        icon_url=GAME_THUMBNAILS[account.game],
                    )
            else:
                raise RuntimeError(f"API {api} returned {resp.status}")
        return embed

    @classmethod
    async def _notify_user(cls, bot: HoyoBuddy, user: User, embed: Embed) -> None:
        try:
            discord_user = await bot.get_or_fetch_user(user.id)
            if discord_user:
                await discord_user.send(embed=embed)
        except discord.HTTPException:
            pass
