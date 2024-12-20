from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar, Literal

import discord
import genshin
from loguru import logger
from seria.utils import create_bullet_list

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import (
    CODE_CHANNEL_IDS,
    GPY_GAME_TO_HB_GAME,
    HB_GAME_TO_GPY_GAME,
    PROXY_APIS,
)
from hoyo_buddy.db.models import HoyoAccount, JSONFile
from hoyo_buddy.embeds import DefaultEmbed, ErrorEmbed
from hoyo_buddy.enums import Platform
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import convert_code_to_redeem_url

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.embeds import Embed
    from hoyo_buddy.types import ProxyAPI


MAX_API_ERROR_COUNT = 10


class AutoRedeem:
    _total_redeem_count: ClassVar[int]
    _bot: ClassVar[HoyoBuddy]
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    async def execute(
        cls, bot: HoyoBuddy, game: genshin.Game | None = None, codes: list[str] | None = None
    ) -> None:
        """Redeem codes for accounts that have auto redeem enabled.

        Args:
            bot: The bot instance.
            game: The game to redeem codes for, all games if None.
            codes: The codes to redeem, None to fetch from API.
        """
        if cls._lock.locked():
            logger.warning("Auto redeem is already running")
            return

        async with cls._lock:
            try:
                logger.info(
                    f"Starting auto redeem task for game {game or 'all'} and codes {codes or 'from API'}"
                )

                cls._total_redeem_count = 0
                cls._bot = bot

                games_to_redeem = (
                    genshin.Game.GENSHIN,
                    genshin.Game.STARRAIL,
                    genshin.Game.ZZZ,
                    genshin.Game.TOT,
                )
                game_codes = (
                    {game: codes}
                    if game is not None and codes is not None
                    else {game_: await cls._get_codes(game_) for game_ in games_to_redeem}
                )
                logger.debug(f"Game codes: {game_codes}")

                if cls._bot.env == "prod":
                    asyncio.create_task(cls.send_codes_to_channels(bot, game_codes))

                if game is None:
                    accounts = await HoyoAccount.filter(auto_redeem=True).all()
                else:
                    accounts = await HoyoAccount.filter(
                        auto_redeem=True, game=GPY_GAME_TO_HB_GAME[game]
                    ).all()

                queue: asyncio.Queue[HoyoAccount] = asyncio.Queue()
                for account in accounts:
                    if (
                        account.platform is Platform.MIYOUSHE
                        or HB_GAME_TO_GPY_GAME[account.game] not in game_codes
                        or not account.can_redeem_code
                    ):
                        continue
                    await queue.put(account)

                tasks = [
                    asyncio.create_task(cls._redeem_code_task(queue, api, game_codes))
                    for api in PROXY_APIS
                ]
                tasks.append(asyncio.create_task(cls._redeem_code_task(queue, "LOCAL", game_codes)))

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                bot.capture_exception(e)
            finally:
                logger.info(
                    f"Auto redeem task completed, total redeem count: {cls._total_redeem_count}"
                )

    @classmethod
    async def send_codes_to_channels(
        cls, bot: HoyoBuddy, game_codes: dict[genshin.Game, list[str]]
    ) -> None:
        guild = bot.get_guild(bot.guild_id) or await bot.fetch_guild(bot.guild_id)
        sent_codes: dict[str, list[str]] = await JSONFile.read("sent_codes.json")

        for game_, codes_ in game_codes.items():
            if game_ not in CODE_CHANNEL_IDS:
                continue

            channel = guild.get_channel(CODE_CHANNEL_IDS[game_])
            if not isinstance(channel, discord.TextChannel):
                continue

            game_sent_codes = sent_codes.get(game_.value, [])
            codes_to_send: list[str] = []
            for code in codes_:
                if code in game_sent_codes:
                    continue

                codes_to_send.append(code)
                game_sent_codes.append(code)

            if codes_to_send:
                codes_to_send = [
                    convert_code_to_redeem_url(code, game=GPY_GAME_TO_HB_GAME[game_])
                    for code in codes_to_send
                ]
                try:
                    message = await channel.send(create_bullet_list(codes_to_send))
                except Exception as e:
                    bot.capture_exception(e)
                    continue
                await message.publish()

            sent_codes[game_.value] = list(set(game_sent_codes))

        await JSONFile.write("sent_codes.json", sent_codes)

    @classmethod
    async def _get_codes(cls, game: genshin.Game) -> list[str]:
        async with cls._bot.session.get(
            f"https://hoyo-codes.seria.moe/codes?game={game.value}"
        ) as resp:
            data = await resp.json()
            return [code["code"] for code in data["codes"]]

    @classmethod
    async def _redeem_code_task(
        cls,
        queue: asyncio.Queue[HoyoAccount],
        api_name: ProxyAPI | Literal["LOCAL"],
        game_codes: dict[genshin.Game, list[str]],
    ) -> None:
        logger.info(f"Auto redeem task started for api: {api_name}")

        bot = cls._bot
        if api_name != "LOCAL":
            # test if the api is working
            async with bot.session.get(PROXY_APIS[api_name]) as resp:
                if resp.status != 200:
                    logger.warning(f"API {api_name} returned {resp.status}")
                    return

        api_error_count = 0

        while True:
            account = await queue.get()
            codes = game_codes[HB_GAME_TO_GPY_GAME[account.game]]

            try:
                await account.fetch_related("user")
                embed = await cls._redeem_codes(api_name, account, codes)
            except Exception as e:
                embed, recognized = get_error_embed(
                    e, account.user.settings.locale or discord.Locale.american_english
                )
                if not recognized:
                    api_error_count += 1
                    await queue.put(account)
                    cls._bot.capture_exception(e)

                if api_error_count >= MAX_API_ERROR_COUNT:
                    logger.warning(f"API {api_name} failed for {api_error_count} accounts")
                    return

            if embed is not None:
                cls._total_redeem_count += 1
                await cls._notify_user(account, embed)

            queue.task_done()

    @classmethod
    async def _notify_user(cls, account: HoyoAccount, embed: Embed) -> None:
        if isinstance(embed, ErrorEmbed):
            embed.add_acc_info(account, blur=False)
            content = LocaleStr(key="auto_redeem_error.content")

            account.auto_redeem = False
            await account.save(update_fields=("auto_redeem",))
        else:
            content = None

        try:
            await cls._bot.dm_user(account.user.id, embed=embed, content=content)
        except Exception as e:
            cls._bot.capture_exception(e)

    @classmethod
    async def _redeem_codes(
        cls, api_name: ProxyAPI | Literal["LOCAL"], account: HoyoAccount, codes: list[str]
    ) -> DefaultEmbed | None:
        await account.user.fetch_related("settings")
        locale = account.user.settings.locale or discord.Locale.american_english
        client = account.client
        client.set_lang(locale)

        embed = await account.client.redeem_codes(
            codes,
            locale=locale,
            blur=False,
            api_url=PROXY_APIS[api_name] if api_name != "LOCAL" else "LOCAL",
        )
        if embed is None:
            return None

        embed.set_footer(text=LocaleStr(key="auto_redeem_footer"))
        return embed
