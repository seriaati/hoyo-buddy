import asyncio
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from ..constants import UID_STARTS
from ..hoyo.auto_tasks.daily_checkin import DailyCheckin
from ..hoyo.auto_tasks.farm_check import FarmChecker
from ..hoyo.auto_tasks.notes_check import NotesChecker
from ..utils import get_now
from .search import Search

if TYPE_CHECKING:
    from ..bot.bot import HoyoBuddy


class Schedule(commands.Cog):
    def __init__(self, bot: "HoyoBuddy") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        if self.bot.env == "dev":
            return
        self.schedule.start()

    async def cog_unload(self) -> None:
        if self.bot.env == "dev":
            return
        self.schedule.cancel()

    loop_interval = 1

    @tasks.loop(minutes=loop_interval)
    async def schedule(self) -> None:
        now = get_now()
        tasks: set[asyncio.Task] = set()
        # Every day at 00:00
        if now.hour == 0 and now.minute < self.loop_interval:
            tasks.add(asyncio.create_task(DailyCheckin.execute(self.bot)))
            tasks.add(asyncio.create_task(self.bot.update_assets()))

        # Every day at 04:00, 11:00, 17:00
        if now.hour in {4, 11, 17} and now.minute < self.loop_interval:
            match now.hour:
                case 11:
                    # Europe server
                    tasks.add(asyncio.create_task(FarmChecker.execute(self.bot, "7")))
                case 17:
                    # America server
                    tasks.add(asyncio.create_task(FarmChecker.execute(self.bot, "6")))
                case _:
                    # Asia, China, and TW/HK/MO servers
                    for uid_start in UID_STARTS:
                        if uid_start in {"7", "6"}:
                            continue
                        tasks.add(asyncio.create_task(FarmChecker.execute(self.bot, uid_start)))

        # Every day at 11:00
        if now.hour == 11 and now.minute < self.loop_interval and self.bot.env != "dev":
            search_cog = self.bot.get_cog("Search")
            if isinstance(search_cog, Search):
                tasks.add(asyncio.create_task(search_cog._setup_search_autocomplete_choices()))

        # Every minute
        if now.minute % 1 < self.loop_interval:
            tasks.add(asyncio.create_task(NotesChecker.execute(self.bot)))

        # Every hour
        if now.minute < self.loop_interval:
            tasks.add(asyncio.create_task(self.bot.translator.push_source_strings()))

        for task in tasks:
            task.add_done_callback(tasks.discard)

    @schedule.before_loop
    async def before_schedule(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "HoyoBuddy") -> None:
    await bot.add_cog(Schedule(bot))
