from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands, tasks
from loguru import logger

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import HoyoBuddy


class HealthCheck(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.send_heartbeat.start()

    async def cog_unload(self) -> None:
        self.send_heartbeat.cancel()

    @tasks.loop(minutes=1)
    async def send_heartbeat(self) -> None:
        url = (
            self.bot.config.main_heartbeat_url
            if self.bot.deployment == "main"
            else self.bot.config.sub_heartbeat_url
        )
        if url is None:
            logger.warning("No heartbeat URL configured, skipping health check.")
            return

        await self.bot.session.get(url)

    @send_heartbeat.before_loop
    async def before_send_heartbeat(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(HealthCheck(bot))
