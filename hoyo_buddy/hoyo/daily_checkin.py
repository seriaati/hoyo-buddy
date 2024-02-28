import asyncio
import logging
import os
from typing import TYPE_CHECKING, ClassVar

import discord
import genshin

from ..bot.error_handler import get_error_embed
from ..bot.translator import LocaleStr, Translator
from ..db.enums import GAME_THUMBNAILS
from ..db.models import HoyoAccount, User
from ..embeds import DefaultEmbed, Embed, ErrorEmbed

if TYPE_CHECKING:
    import aiohttp

    from ..bot.bot import HoyoBuddy

LOGGER_ = logging.getLogger(__name__)

CHECKIN_APIS: dict[str, str] = {
    "VERCEL": "https://daily-checkin-api.vercel.app",
    "DETA": "https://dailycheckin-1-e3972598.deta.app",
    "RENDER": "https://daily-checkin-api.onrender.com",
}
API_TOKEN = os.environ["DAILY_CHECKIN_API_TOKEN"]
MAX_API_ERROR_COUNT = 10


class DailyCheckin:
    _total_checkin_count: ClassVar[int]

    @classmethod
    async def execute(cls, bot: "HoyoBuddy") -> None:
        try:
            LOGGER_.info("Daily check-in started")

            cls._total_checkin_count = 0
            queue: asyncio.Queue[HoyoAccount] = asyncio.Queue()
            accounts = await HoyoAccount.filter(daily_checkin=True)
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
        except Exception as e:
            bot.capture_exception(e)
        finally:
            LOGGER_.info(
                "Daily check-in finished, total check-in count: %d", cls._total_checkin_count
            )

    @classmethod
    async def _daily_checkin_task(
        cls, queue: asyncio.Queue[HoyoAccount], api_name: str, bot: "HoyoBuddy"
    ) -> None:
        LOGGER_.info("Daily check-in task started for api: %s", api_name)
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
                LOGGER_.exception("Daily check-in failed for %s", account)
                if api_error_count >= MAX_API_ERROR_COUNT:
                    msg = f"Daily check-in API {api_name} failed for {api_error_count} accounts"
                    raise RuntimeError(msg) from None
            else:
                cls._total_checkin_count += 1
                await account.fetch_related("notif_settings")
                if (
                    isinstance(embed, ErrorEmbed)
                    and account.notif_settings.notify_on_checkin_failure
                ) or (
                    isinstance(embed, DefaultEmbed)
                    and account.notif_settings.notify_on_checkin_success
                ):
                    await cls._notify_user(bot, account.user, embed)
            finally:
                await asyncio.sleep(2.0)
                queue.task_done()

    @classmethod
    async def _daily_checkin(
        cls,
        api_name: str,
        account: HoyoAccount,
        translator: Translator,
        session: "aiohttp.ClientSession",
    ) -> Embed:
        LOGGER_.debug("Daily check-in with %s for %s", api_name, account)

        await account.user.fetch_related("settings")

        locale = account.user.settings.locale or discord.Locale.american_english
        client = account.client
        assert client.game is not None
        client.set_lang(locale)

        if api_name == "LOCAL":
            try:
                reward = await client.claim_daily_reward()
            except Exception as e:
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
        api_url = CHECKIN_APIS[api_name]
        async with session.post(f"{api_url}/checkin/", json=payload) as resp:
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
                msg = f"API {api_name} returned {resp.status}"
                raise RuntimeError(msg)

        return embed

    @classmethod
    async def _notify_user(cls, bot: "HoyoBuddy", user: User, embed: Embed) -> None:
        discord_user = await bot.fetch_user(user.id)
        if discord_user:
            try:
                await discord_user.send(embed=embed)
            except discord.DiscordException:
                LOGGER_.exception("Failed to send daily check-in notification to %s", discord_user)
