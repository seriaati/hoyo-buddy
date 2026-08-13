from __future__ import annotations

import asyncio
import datetime
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar

import discord
from loguru import logger
from seria.utils import shorten

from hoyo_buddy.constants import AUTO_TASK_FEATURE_KEYS, NOTIF_SETTING_FIELDS
from hoyo_buddy.db.models import AccountNotifSettings, DiscordEmbed, Settings
from hoyo_buddy.enums import Locale
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import get_now, sleep

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import HoyoBuddy
    from hoyo_buddy.db.models import HoyoAccount
    from hoyo_buddy.types import AutoTaskType

MAX_EMBEDS_PER_MESSAGE = 10
MAX_EMBED_CHARS_PER_MESSAGE = 5900
STALE_EMBED_HOURS = 12


class EmbedSender:
    _bot: ClassVar[HoyoBuddy]
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    def _get_error_content(
        cls, task_type: AutoTaskType, locale: Locale | None, account: HoyoAccount
    ) -> str | None:
        feature_key = AUTO_TASK_FEATURE_KEYS.get(task_type)
        if feature_key is None:
            return None

        if "mimo" in task_type:
            return LocaleStr(
                key="auto_task_error_dm_content",
                feature=LocaleStr(
                    custom_str="{mimo_title} {label}",
                    mimo_title=LocaleStr(key="point_detail_tag_mimo", mi18n_game="mimo"),
                    label=LocaleStr(key=feature_key),
                ),
                command="</settings>",
                account=account,
            ).translate(locale or Locale.american_english)
        return LocaleStr(
            key="auto_task_error_dm_content",
            feature=LocaleStr(key=feature_key),
            command="</settings>",
            account=account,
        ).translate(locale or Locale.american_english)

    @classmethod
    async def _get_locale(cls, user_id: int) -> Locale | None:
        settings = await Settings.get(user_id=user_id)
        return Locale(settings.lang) if settings.lang else None

    @classmethod
    def _is_notify_enabled(
        cls, embed: DiscordEmbed, notif_settings: AccountNotifSettings | None
    ) -> bool:
        notif_fields = NOTIF_SETTING_FIELDS.get(embed.task_type, ())
        if len(notif_fields) < 2 or notif_settings is None:
            return True

        field = notif_fields[0] if embed.type == "default" else notif_fields[1]
        return bool(getattr(notif_settings, field))

    @classmethod
    def _chunk_embeds(
        cls, items: list[tuple[DiscordEmbed, discord.Embed]]
    ) -> list[list[tuple[DiscordEmbed, discord.Embed]]]:
        chunks: list[list[tuple[DiscordEmbed, discord.Embed]]] = []
        current: list[tuple[DiscordEmbed, discord.Embed]] = []
        total_chars = 0

        for row, embed in items:
            if current and (
                len(current) >= MAX_EMBEDS_PER_MESSAGE
                or total_chars + len(embed) > MAX_EMBED_CHARS_PER_MESSAGE
            ):
                chunks.append(current)
                current = []
                total_chars = 0

            current.append((row, embed))
            total_chars += len(embed)

        if current:
            chunks.append(current)
        return chunks

    @classmethod
    async def _send_embeds(
        cls,
        user_id: int,
        embeds: list[DiscordEmbed],
        notif_settings: dict[int, AccountNotifSettings],
    ) -> int:
        """Send queued embeds to a user in batches, returns the number of deleted rows."""
        deleted = 0
        to_send: list[tuple[DiscordEmbed, discord.Embed]] = []
        locale: Locale | None = None

        for embed in embeds:
            if not cls._is_notify_enabled(embed, notif_settings.get(embed.account_id)):
                deleted += await DiscordEmbed.filter(id=embed.id).delete()
                continue

            dc_embed = discord.Embed.from_dict(embed.data)
            if embed.type == "error":
                locale = locale or await cls._get_locale(user_id)
                content = cls._get_error_content(embed.task_type, locale, embed.account)
                if content is not None:
                    dc_embed.description = shorten(
                        f"{dc_embed.description}\n\n{content}" if dc_embed.description else content,
                        4096,
                    )

            to_send.append((embed, dc_embed))

        for chunk in cls._chunk_embeds(to_send):
            _, errored = await cls._bot.dm_user(user_id, embeds=[e for _, e in chunk])
            await sleep("dm")
            if not errored:
                deleted += await DiscordEmbed.filter(id__in=[row.id for row, _ in chunk]).delete()

        return deleted

    @classmethod
    async def execute(cls, bot: HoyoBuddy) -> None:
        if cls._lock.locked():
            logger.debug(f"{cls.__name__} is already running")
            return

        async with cls._lock:
            try:
                cls._bot = bot

                stale = await DiscordEmbed.filter(
                    type="default",
                    created_at__lt=get_now() - datetime.timedelta(hours=STALE_EMBED_HOURS),
                ).delete()
                if stale:
                    logger.info(f"{cls.__name__} deleted {stale} stale embeds")

                cnt = await DiscordEmbed.all().count()
                if cnt == 0:
                    return

                logger.info(f"Starting {cls.__name__} for {cnt} embeds")

                while True:
                    embeds = (
                        await DiscordEmbed.all()
                        .order_by("-type", "id")
                        .limit(100)
                        .prefetch_related("account")
                    )
                    if not embeds:
                        logger.debug("No embeds to send for")
                        break

                    notif_settings = {
                        settings.account_id: settings
                        for settings in await AccountNotifSettings.filter(
                            account_id__in={embed.account_id for embed in embeds}
                        )
                    }

                    # Organize embeds into a dictionary with user_id as key
                    embeds_dict: defaultdict[int, list[DiscordEmbed]] = defaultdict(list)
                    for embed in embeds:
                        embeds_dict[embed.user_id].append(embed)

                    deleted = 0
                    for user_id, user_embeds in embeds_dict.items():
                        deleted += await cls._send_embeds(user_id, user_embeds, notif_settings)

                    if deleted == 0:
                        # Every send in this batch errored, break to avoid spinning on them
                        break
            except Exception as e:
                bot.capture_exception(e)
