from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar, Literal

import discord
import genshin
from loguru import logger
from seria.utils import create_bullet_list

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import CODE_CHANNEL_IDS, HB_GAME_TO_GPY_GAME, PROXY_APIS
from hoyo_buddy.db import HoyoAccount, JSONFile
from hoyo_buddy.embeds import DefaultEmbed, ErrorEmbed
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import convert_code_to_redeem_url, get_now

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.embeds import Embed
    from hoyo_buddy.types import ProxyAPI


SUPPORT_GAMES = (Game.GENSHIN, Game.STARRAIL, Game.ZZZ)
MAX_API_ERROR_COUNT = 10


class AutoRedeem:
    _count: ClassVar[int]
    _bot: ClassVar[HoyoBuddy]
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    async def execute(cls, bot: HoyoBuddy) -> None:
        """Redeem codes for accounts that have auto redeem enabled."""
        if cls._lock.locked():
            logger.debug(f"{cls.__name__} is already running")
            return

        async with cls._lock:
            start = asyncio.get_event_loop().time()

            try:
                cls._count = 0
                cls._bot = bot

                game_codes = {game_: await cls._get_codes(game_) for game_ in SUPPORT_GAMES}
                logger.debug(f"Game codes: {game_codes}")

                if not cls._bot.config.is_dev:
                    asyncio.create_task(cls.send_codes_to_channels(bot, game_codes))

                queue = await cls._bot.build_auto_task_queue(
                    "redeem", games=SUPPORT_GAMES, region=genshin.Region.OVERSEAS
                )
                if queue.empty():
                    logger.debug(f"Queue is empty for {cls.__name__}")
                    return

                logger.info(f"Starting {cls.__name__} for {queue.qsize()} accounts")
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
            else:
                logger.info(f"{cls.__name__} completed, total count: {cls._count}")
                logger.info(f"{cls.__name__} took {asyncio.get_event_loop().time() - start:.2f}s")

    @classmethod
    async def send_codes_to_channels(
        cls, bot: HoyoBuddy, game_codes: dict[Game, list[str]]
    ) -> None:
        guild = bot.get_guild(bot.guild_id) or await bot.fetch_guild(bot.guild_id)
        sent_codes: dict[str, list[str]] = await JSONFile.read("sent_codes.json")

        for game, codes in game_codes.items():
            if game not in CODE_CHANNEL_IDS:
                continue

            channel = guild.get_channel(CODE_CHANNEL_IDS[game])
            if not isinstance(channel, discord.TextChannel):
                continue

            game_sent_codes = sent_codes.get(HB_GAME_TO_GPY_GAME[game].value, [])
            codes_to_send: list[str] = []
            for code in codes:
                if code in game_sent_codes:
                    continue

                codes_to_send.append(code)
                game_sent_codes.append(code)

            if codes_to_send:
                codes_to_send = [
                    convert_code_to_redeem_url(code, game=game) for code in codes_to_send
                ]
                try:
                    message = await channel.send(create_bullet_list(codes_to_send))
                except Exception as e:
                    bot.capture_exception(e)
                    continue
                await message.publish()

            sent_codes[HB_GAME_TO_GPY_GAME[game].value] = list(set(game_sent_codes))

        await JSONFile.write("sent_codes.json", sent_codes)

    @classmethod
    async def _get_codes(cls, game: Game) -> list[str]:
        async with cls._bot.session.get(
            f"https://hoyo-codes.seria.moe/codes?game={HB_GAME_TO_GPY_GAME[game].value}"
        ) as resp:
            data = await resp.json()
            return [code["code"] for code in data["codes"]]

    @classmethod
    async def _redeem_code_task(
        cls,
        queue: asyncio.Queue[HoyoAccount],
        api_name: ProxyAPI | Literal["LOCAL"],
        game_codes: dict[Game, list[str]],
    ) -> None:
        logger.info(f"Auto redeem task started for api: {api_name}")

        bot = cls._bot
        if api_name != "LOCAL":
            try:
                async with bot.session.get(PROXY_APIS[api_name]) as resp:
                    resp.raise_for_status()
            except Exception as e:
                logger.warning(f"Failed to connect to {api_name}")
                bot.capture_exception(e)

        api_error_count = 0

        while True:
            account = await queue.get()
            logger.debug(f"{cls.__name__} is processing account {account}")
            codes = game_codes.get(account.game, [])
            if not codes:
                logger.debug(f"No codes for {account}, game={account.game}, marking task as done")
                queue.task_done()
                continue

            try:
                await account.fetch_related("user", "user__settings")
                embed = await cls._redeem_codes(api_name, account, codes)
            except Exception as e:
                api_error_count += 1
                await queue.put(account)
                cls._bot.capture_exception(e)

                if api_error_count >= MAX_API_ERROR_COUNT:
                    logger.warning(f"API {api_name} failed for {api_error_count} accounts")
                    return
            else:
                logger.debug(f"Setting last time for {account}, now={get_now()}")
                account.last_redeem_time = get_now()
                await account.save(update_fields=("last_redeem_time",))

                if embed is not None:
                    cls._count += 1
                    await cls._notify_user(account, embed)
            finally:
                queue.task_done()

    @classmethod
    async def _notify_user(cls, account: HoyoAccount, embed: Embed) -> None:
        try:
            if isinstance(embed, ErrorEmbed):
                embed.add_acc_info(account, blur=False)
                content = LocaleStr(
                    key="auto_task_error_dm_content",
                    feature=LocaleStr(key="auto_redeem_toggle.label"),
                    command="</redeem>",
                ).translate(account.user.settings.locale or discord.Locale.american_english)

                account.auto_redeem = False
                await account.save(update_fields=("auto_redeem",))
            else:
                content = None

            await cls._bot.dm_user(account.user.id, embed=embed, content=content)
        except Exception as e:
            cls._bot.capture_exception(e)

    @classmethod
    async def _redeem_codes(
        cls, api_name: ProxyAPI | Literal["LOCAL"], account: HoyoAccount, codes: list[str]
    ) -> DefaultEmbed | ErrorEmbed | None:
        locale = account.user.settings.locale or discord.Locale.american_english

        try:
            client = account.client
            client.set_lang(locale)

            embed = await account.client.redeem_codes(
                codes, locale=locale, blur=False, api_name=api_name
            )
            if embed is None:
                return None

            embed.set_footer(text=LocaleStr(key="auto_redeem_footer"))
        except Exception as e:
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                raise
            embed.add_acc_info(account, blur=False)
            return embed
        else:
            return embed
