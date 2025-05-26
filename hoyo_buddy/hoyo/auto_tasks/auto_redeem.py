from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar

import discord
import genshin
from loguru import logger
from seria.utils import create_bullet_list

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import (
    CODE_CHANNEL_IDS,
    CONCURRENT_TASK_NUM,
    HB_GAME_TO_GPY_GAME,
    MAX_PROXY_ERROR_NUM,
)
from hoyo_buddy.db import HoyoAccount, JSONFile
from hoyo_buddy.db.models import DiscordEmbed
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import convert_code_to_redeem_url, error_handler, get_now

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.embeds import DefaultEmbed, ErrorEmbed


SUPPORT_GAMES = (Game.GENSHIN, Game.STARRAIL, Game.ZZZ)


class AutoRedeem:
    _count: ClassVar[int]
    _bot: ClassVar[HoyoBuddy]
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _error_counts: ClassVar[defaultdict[int, int]]

    @classmethod
    async def execute(cls, bot: HoyoBuddy, *, skip_redeemed: bool = True) -> None:
        """Redeem codes for accounts that have auto redeem enabled."""
        if cls._lock.locked():
            logger.debug(f"{cls.__name__} is already running")
            return

        async with cls._lock:
            start = asyncio.get_event_loop().time()

            try:
                cls._count = 0
                cls._bot = bot
                cls._error_counts = defaultdict(int)

                game_codes = {game_: await cls._get_codes(game_) for game_ in SUPPORT_GAMES}
                logger.debug(f"Game codes: {game_codes}")

                if not cls._bot.config.is_dev:
                    asyncio.create_task(cls._send_codes_to_channels(bot, game_codes))

                queue = await cls._bot.build_auto_task_queue(
                    "redeem", games=SUPPORT_GAMES, region=genshin.Region.OVERSEAS
                )
                if queue.empty():
                    logger.debug(f"Queue is empty for {cls.__name__}")
                    return

                logger.info(f"Starting {cls.__name__} for {queue.qsize()} accounts")
                tasks = [
                    asyncio.create_task(
                        cls._redeem_code_task(queue, game_codes, skip_redeemed=skip_redeemed)
                    )
                    for _ in range(CONCURRENT_TASK_NUM)
                ]

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                bot.capture_exception(e)
            else:
                logger.info(f"{cls.__name__} completed, count={cls._count}")
                logger.info(f"{cls.__name__} took {asyncio.get_event_loop().time() - start:.2f}s")

    @classmethod
    async def _send_codes_to_channels(
        cls, bot: HoyoBuddy, game_codes: dict[Game, list[str]]
    ) -> None:
        guild = await bot.get_or_fetch_guild()
        if guild is None:
            logger.warning(f"{cls.__name__} cannot get guild, skipping code sending")
            return

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
        game_codes: dict[Game, list[str]],
        *,
        skip_redeemed: bool,
    ) -> None:
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
                embed = await cls._redeem_codes(account, codes, skip_redeemed=skip_redeemed)
            except Exception as e:
                with error_handler():
                    if cls._error_counts[account.id] >= MAX_PROXY_ERROR_NUM:
                        locale = account.user.settings.locale or discord.Locale.american_english
                        embed, _ = get_error_embed(e, locale)
                        embed.add_acc_info(account, blur=False)
                        await DiscordEmbed.create(
                            embed,
                            user_id=account.user.id,
                            account_id=account.id,
                            task_type="redeem",
                        )
                    else:
                        cls._error_counts[account.id] += 1
                        cls._bot.capture_exception(e)
                        await queue.put(account)
            else:
                logger.debug(f"Setting last time for {account}, now={get_now()}")
                account.last_redeem_time = get_now()
                await account.save(update_fields=("last_redeem_time",))

                if embed is not None:
                    cls._count += 1
                    await DiscordEmbed.create(
                        embed, user_id=account.user.id, account_id=account.id, task_type="redeem"
                    )
            finally:
                queue.task_done()

    @classmethod
    async def _redeem_codes(
        cls, account: HoyoAccount, codes: list[str], *, skip_redeemed: bool
    ) -> DefaultEmbed | ErrorEmbed | None:
        locale = account.user.settings.locale or discord.Locale.american_english

        try:
            client = account.client
            client.use_proxy = True
            client.set_lang(locale)

            embed = await account.client.redeem_codes(
                codes, locale=locale, blur=False, skip_redeemed=skip_redeemed
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
