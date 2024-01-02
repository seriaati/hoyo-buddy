import logging
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

import discord
import sentry_sdk
from asyncache import cached
from cachetools import TTLCache
from discord.ext import commands

from .command_tree import CommandTree
from .translator import AppCommandTranslator, Translator

if TYPE_CHECKING:
    from aiohttp import ClientSession

log = logging.getLogger(__name__)

__all__ = ("HoyoBuddy", "INTERACTION")

INTERACTION: TypeAlias = discord.Interaction["HoyoBuddy"]

intents = discord.Intents(
    guilds=True,
    members=True,
    emojis=True,
    messages=True,
)
allowed_mentions = discord.AllowedMentions(
    users=True,
    everyone=False,
    roles=False,
    replied_user=False,
)


class HoyoBuddy(commands.AutoShardedBot):
    def __init__(
        self,
        *,
        session: "ClientSession",
        env: str,
        translator: Translator,
    ) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            case_insensitive=True,
            allowed_mentions=allowed_mentions,
            help_command=None,
            chunk_guilds_at_startup=False,
            max_messages=None,
            member_cache_flags=discord.MemberCacheFlags.none(),
            tree_cls=CommandTree,
        )
        self.session = session
        self.uptime = discord.utils.utcnow()
        self.translator = translator
        self.env = env

    async def setup_hook(self) -> None:
        await self.tree.set_translator(AppCommandTranslator(self.translator))

        for filepath in Path("hoyo_buddy/cogs").glob("**/*.py"):
            cog_name = Path(filepath).stem
            try:
                await self.load_extension(f"hoyo_buddy.cogs.{cog_name}")
                log.info("Loaded cog %r", cog_name)
            except Exception:  # skipcq: PYL-W0703
                log.exception("Failed to load cog %r", cog_name)

        await self.load_extension("jishaku")

    def capture_exception(self, e: Exception) -> None:
        if self.env == "prod":
            sentry_sdk.capture_exception(e)
        else:
            log.exception(e)

    @cached(cache=TTLCache(maxsize=1024, ttl=360))
    async def get_or_fetch_user(self, user_id: int) -> discord.User | None:
        user = self.get_user(user_id)
        if user:
            return user

        try:
            user = await self.fetch_user(user_id)
        except discord.HTTPException:
            return None
        else:
            return user

    async def close(self) -> None:
        log.info("Bot shutting down...")
        await super().close()
