import logging
from pathlib import Path

import discord
from aiohttp import ClientSession
from discord.ext import commands

log = logging.getLogger(__name__)


class HoyoBuddy(commands.AutoShardedBot):
    def __init__(
        self,
        *args,
        session: ClientSession,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.session = session
        self.uptime = discord.utils.utcnow()

    async def setup_hook(self):
        for filepath in Path("./cogs").glob("**/*.py"):
            cog_name = Path(filepath).stem
            try:
                await self.load_extension(f"hoyo_buddy.cogs.{cog_name}")
            except Exception as e:  # skipcq: PYL-W0703
                log.error(f"Failed to load cog {cog_name}: {e}", exc_info=True)

        await self.load_extension("jishaku")
