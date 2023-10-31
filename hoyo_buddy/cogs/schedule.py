import asyncio

from discord.ext import commands, tasks

from ..bot import HoyoBuddy
from ..hoyo.daily_checkin import DailyCheckin
from ..utils import get_now


class Schedule(commands.Cog):
    def __init__(self, bot: HoyoBuddy):
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
            asyncio.create_task(DailyCheckin.exec(self.bot))

    @schedule.before_loop
    async def before_schedule(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: HoyoBuddy):
    await bot.add_cog(Schedule(bot))
