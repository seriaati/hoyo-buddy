import asyncio
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from ..hoyo.daily_checkin import DailyCheckin
from ..utils import get_now

if TYPE_CHECKING:
    from ..bot.bot import HoyoBuddy


class Schedule(commands.Cog):
    def __init__(self, bot: "HoyoBuddy") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.schedule.start()

    async def cog_unload(self) -> None:
        self.schedule.cancel()

    loop_interval = 1

    @tasks.loop(minutes=loop_interval)
    async def schedule(self) -> None:
        now = get_now()
        if now.hour == 0 and now.minute < self.loop_interval:
            asyncio.create_task(DailyCheckin.execute(self.bot))

    @schedule.before_loop
    async def before_schedule(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "HoyoBuddy") -> None:
    await bot.add_cog(Schedule(bot))
