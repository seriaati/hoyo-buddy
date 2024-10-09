from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from ..constants import GI_UID_PREFIXES, UTC_8
from ..hoyo.auto_tasks.auto_redeem import AutoRedeem
from ..hoyo.auto_tasks.daily_checkin import DailyCheckin
from ..hoyo.auto_tasks.farm_check import FarmChecker
from ..hoyo.auto_tasks.notes_check import NotesChecker
from ..utils import get_now
from .search import Search

if TYPE_CHECKING:
    from ..bot import HoyoBuddy


class Schedule(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        if not self.bot.config.schedule:
            return

        self.run_daily_checkin.start()
        self.run_farm_checks.start()
        self.update_search_autofill.start()
        self.update_assets.start()
        self.run_notes_check.start()
        self.run_auto_redeem.start()

    async def cog_unload(self) -> None:
        if not self.bot.config.schedule:
            return

        self.run_daily_checkin.cancel()
        self.run_farm_checks.cancel()
        self.update_search_autofill.cancel()
        self.update_assets.cancel()
        self.run_notes_check.cancel()
        self.run_auto_redeem.cancel()

    @tasks.loop(time=datetime.time(0, 0, 0, tzinfo=UTC_8))
    async def run_daily_checkin(self) -> None:
        await DailyCheckin.execute(self.bot)

    @tasks.loop(time=[datetime.time(hour, 0, 0, tzinfo=UTC_8) for hour in (4, 11, 17)])
    async def run_farm_checks(self) -> None:
        hour = get_now().hour
        if hour == 11:
            await FarmChecker.execute(self.bot, "7")
        elif hour == 17:
            await FarmChecker.execute(self.bot, "6")
        else:
            for uid_start in GI_UID_PREFIXES:
                if uid_start in {"7", "6"}:
                    continue
                await FarmChecker.execute(self.bot, uid_start)

    @tasks.loop(time=datetime.time(11, 0, 0, tzinfo=UTC_8))
    async def update_search_autofill(self) -> None:
        if not self.bot.config.search_autocomplete:
            return

        search_cog = self.bot.get_cog("Search")
        if isinstance(search_cog, Search):
            await search_cog._setup_search_autofill()

    @tasks.loop(time=datetime.time(11, 0, 0, tzinfo=UTC_8))
    async def update_assets(self) -> None:
        await self.bot.update_assets()

    @tasks.loop(minutes=1)
    async def run_notes_check(self) -> None:
        await NotesChecker.execute(self.bot)

    @tasks.loop(hours=1)
    async def run_auto_redeem(self) -> None:
        await AutoRedeem.execute(self.bot)

    @run_daily_checkin.before_loop
    @run_farm_checks.before_loop
    @update_search_autofill.before_loop
    @update_assets.before_loop
    @run_notes_check.before_loop
    @run_auto_redeem.before_loop
    async def before_loops(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Schedule(bot))
