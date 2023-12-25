import logging
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

import discord
import sentry_sdk
from discord.ext import commands

from .translator import AppCommandTranslator, Translator

if TYPE_CHECKING:
    from aiohttp import ClientSession

log = logging.getLogger(__name__)

__all__ = ("HoyoBuddy", "INTERACTION")

INTERACTION: TypeAlias = discord.Interaction["HoyoBuddy"]


class HoyoBuddy(commands.AutoShardedBot):
    def __init__(
        self,
        *,
        session: "ClientSession",
        env: str,
        translator: Translator,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
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
        log.info("Shutting down...")
        await super().close()
