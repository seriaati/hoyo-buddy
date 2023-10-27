import logging
from pathlib import Path

import discord
from aiohttp import ClientSession
from discord.ext import commands

from .translator import AppCommandTranslator, Translator

log = logging.getLogger(__name__)


class HoyoBuddy(commands.AutoShardedBot):
    def __init__(
        self,
        *args,
        session: ClientSession,
        env: str,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.session = session
        self.uptime = discord.utils.utcnow()
        self.translator = Translator(env)
        self.env = env

    async def setup_hook(self):
        await self.translator.load()
        await self.tree.set_translator(AppCommandTranslator(self.translator))

        for filepath in Path("hoyo_buddy/cogs").glob("**/*.py"):
            cog_name = Path(filepath).stem
            try:
                await self.load_extension(f"hoyo_buddy.cogs.{cog_name}")
                log.info("Loaded cog %r", cog_name)
            except Exception:  # skipcq: PYL-W0703
                log.error("Failed to load cog %r", cog_name, exc_info=True)

        await self.load_extension("jishaku")

    async def close(self):
        log.info("Shutting down...")
        await self.translator.unload()
        await super().close()
