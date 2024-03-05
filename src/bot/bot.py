import logging
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

import discord
import diskcache
import sentry_sdk
from asyncache import cached
from cachetools import TTLCache
from discord.ext import commands, tasks

from ..utils import get_now
from .command_tree import CommandTree
from .translator import AppCommandTranslator, Translator

if TYPE_CHECKING:
    from aiohttp import ClientSession

LOGGER_ = logging.getLogger(__name__)

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
        self.uptime = get_now()
        self.translator = translator
        self.env = env
        self.diskcache = diskcache.Cache("./.cache/hoyo_buddy")

    async def setup_hook(self) -> None:
        await self.tree.set_translator(AppCommandTranslator(self.translator))

        for filepath in Path("src/cogs").glob("**/*.py"):
            cog_name = Path(filepath).stem
            try:
                await self.load_extension(f"src.cogs.{cog_name}")
                LOGGER_.info("Loaded cog %r", cog_name)
            except Exception:
                LOGGER_.exception("Failed to load cog %r", cog_name)

        await self.load_extension("jishaku")

        self.push_source_strings.start()

    def capture_exception(self, e: Exception) -> None:
        if self.env == "prod":
            sentry_sdk.capture_exception(e)
        else:
            LOGGER_.exception(e)

    @cached(cache=TTLCache(maxsize=1024, ttl=360))
    async def fetch_user(self, user_id: int) -> discord.User | None:
        try:
            user = await super().fetch_user(user_id)
        except (discord.NotFound, discord.HTTPException):
            return None
        else:
            return user

    @tasks.loop(minutes=30)
    async def push_source_strings(self) -> None:
        if self.env in {"prod", "test"}:
            await self.translator.push_source_strings()

    async def close(self) -> None:
        LOGGER_.info("Bot shutting down...")
        self.push_source_strings.cancel()
        self.diskcache.close()
        await super().close()
