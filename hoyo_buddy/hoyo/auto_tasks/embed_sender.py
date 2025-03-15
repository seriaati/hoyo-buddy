from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar

import discord
from loguru import logger

from hoyo_buddy.constants import AUTO_TASK_COMMANDS, AUTO_TASK_FEATURE_KEYS
from hoyo_buddy.db.models import DiscordEmbed, HoyoAccount, Settings
from hoyo_buddy.emojis import get_game_emoji
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import sleep

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import HoyoBuddy
    from hoyo_buddy.types import AutoTaskType


class EmbedSender:
    _bot: ClassVar[HoyoBuddy]
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    def _get_error_content(
        cls, task_type: AutoTaskType, locale: discord.Locale | None, account_str: str
    ) -> str | None:
        feature_key = AUTO_TASK_FEATURE_KEYS.get(task_type)
        if feature_key is None:
            return None

        command = AUTO_TASK_COMMANDS.get(task_type)
        if command is None:
            return None

        if "mimo" in task_type:
            return LocaleStr(
                key="auto_task_error_dm_content",
                feature=LocaleStr(
                    custom_str="{mimo_title} {label}",
                    mimo_title=LocaleStr(key="point_detail_tag_mimo", mi18n_game="mimo"),
                    label=LocaleStr(key=feature_key),
                ),
                command=command,
                account=account_str,
            ).translate(locale or discord.Locale.american_english)
        return LocaleStr(
            key="auto_task_error_dm_content",
            feature=LocaleStr(key=feature_key),
            command=command,
            account=account_str,
        ).translate(locale or discord.Locale.american_english)

    @classmethod
    async def _get_locale(cls, user_id: int) -> discord.Locale | None:
        settings = await Settings.get(user_id=user_id).only("lang")
        return discord.Locale(settings.lang) if settings.lang else None

    @classmethod
    async def _get_account_str(cls, account_id: int) -> str:
        account = await HoyoAccount.get(id=account_id).only("game", "uid", "nickname", "username")
        emoji = get_game_emoji(account.game)
        return f"{emoji} {account}"

    @classmethod
    async def _send_embeds(cls, user_id: int, embeds: list[DiscordEmbed]) -> None:
        for embed in embeds:
            if embed.type == "error":
                locale = await cls._get_locale(user_id)
                account_str = await cls._get_account_str(embed.account_id)
                content = cls._get_error_content(embed.task_type, locale, account_str)
            else:
                content = None

            _, errored = await cls._bot.dm_user(
                user_id, embed=discord.Embed.from_dict(embed.data), content=content
            )
            await sleep("dm")
            if not errored:
                await DiscordEmbed.filter(id=embed.id).delete()

    @classmethod
    async def execute(cls, bot: HoyoBuddy) -> None:
        if cls._lock.locked():
            logger.debug(f"{cls.__name__} is already running")
            return

        async with cls._lock:
            try:
                cls._bot = bot

                embeds = await DiscordEmbed.all()
                if not embeds:
                    logger.debug("No embeds to send for")
                    return

                # Organize embeds into a dictionary with user_id as key
                embeds_dict: defaultdict[int, list[DiscordEmbed]] = defaultdict(list)
                for embed in embeds:
                    embeds_dict[embed.user_id].append(embed)

                for user_id, user_embeds in embeds_dict.items():
                    await cls._send_embeds(user_id, user_embeds)
            except Exception as e:
                bot.capture_exception(e)
