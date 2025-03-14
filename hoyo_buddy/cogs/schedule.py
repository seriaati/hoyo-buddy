from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING, Any

from discord import ui
from discord.ext import commands, tasks

from hoyo_buddy.db import HoyoAccount
from hoyo_buddy.hoyo.auto_tasks.auto_mimo import AutoMimoBuy, AutoMimoDraw, AutoMimoTask
from hoyo_buddy.hoyo.auto_tasks.embed_sender import EmbedSender
from hoyo_buddy.hoyo.auto_tasks.web_events_notify import WebEventsNotify

from ..constants import GI_UID_PREFIXES, UTC_8
from ..hoyo.auto_tasks.auto_redeem import AutoRedeem
from ..hoyo.auto_tasks.daily_checkin import DailyCheckin
from ..hoyo.auto_tasks.farm_check import FarmChecker
from ..hoyo.auto_tasks.notes_check import NotesChecker
from ..utils import get_now

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..bot import HoyoBuddy


class RunTaskButton(ui.Button):
    def __init__(self, task_cls: Any) -> None:
        super().__init__(label=task_cls.__name__)
        self.task_cls = task_cls

    async def callback(self, i: Interaction) -> None:
        await i.response.send_message(f"{self.task_cls.__name__} task started")
        asyncio.create_task(self.task_cls.execute(i.client))


class RunTaskView(ui.View):
    def __init__(self) -> None:
        super().__init__()
        tasks = (
            DailyCheckin,
            NotesChecker,
            AutoRedeem,
            AutoMimoTask,
            AutoMimoBuy,
            AutoMimoDraw,
            WebEventsNotify,
            EmbedSender,
        )
        for task in tasks:
            self.add_item(RunTaskButton(task))

    async def interaction_check(self, i: Interaction) -> bool:
        return await i.client.is_owner(i.user)

    @ui.button(label="FarmChecker")
    async def farm_check(self, i: Interaction, _: ui.Button) -> None:
        await i.response.send_message("FarmChecker task started")
        for uid_start in GI_UID_PREFIXES:
            asyncio.create_task(FarmChecker(i.client).execute(uid_start))


class Schedule(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        if not self.bot.config.schedule:
            return

        self.run_auto_tasks.start()
        self.run_send_embeds.start()
        self.run_farm_checks.start()
        self.update_assets.start()
        self.run_notes_check.start()
        self.run_web_events_notify.start()

    async def cog_unload(self) -> None:
        if not self.bot.config.schedule:
            return

        self.run_auto_tasks.cancel()
        self.run_send_embeds.cancel()
        self.run_farm_checks.cancel()
        self.update_assets.cancel()
        self.run_notes_check.cancel()
        self.run_web_events_notify.cancel()

    async def _reset_mimo_all_claimed_time(self) -> None:
        utc_now = get_now(datetime.UTC)
        await (
            HoyoAccount.filter(mimo_all_claimed_time__isnull=False)
            .exclude(mimo_all_claimed_time__day=utc_now.day)
            .update(mimo_all_claimed_time=None)
        )

    @commands.is_owner()
    @commands.command(name="task-status", aliases=["ts"])
    async def task_status(self, ctx: commands.Context) -> None:
        tasks = (AutoRedeem, AutoMimoTask, AutoMimoBuy, AutoMimoDraw, DailyCheckin, EmbedSender)
        task_statuses = {task.__name__: task._lock.locked() for task in tasks}
        msg = "\n".join(f"{task} running: {status}" for task, status in task_statuses.items())
        msg += f"\nFarmChecker running: {self.bot.farm_check_running}"
        await ctx.send(msg)

    @commands.is_owner()
    @commands.command(name="run-task", aliases=["rt"])
    async def run_task(self, ctx: commands.Context) -> None:
        await ctx.send("Select a task to run", view=RunTaskView())

    @tasks.loop(minutes=10)
    async def run_auto_tasks(self) -> None:
        # Mimo
        await self._reset_mimo_all_claimed_time()
        asyncio.create_task(AutoMimoTask.execute(self.bot))
        asyncio.create_task(AutoMimoBuy.execute(self.bot))
        asyncio.create_task(AutoMimoDraw.execute(self.bot))

        # Redeem
        asyncio.create_task(AutoRedeem.execute(self.bot))

        # Check-in
        asyncio.create_task(DailyCheckin.execute(self.bot))

    @tasks.loop(time=[datetime.time(hour, 0, 0, tzinfo=UTC_8) for hour in (4, 11, 17)])
    async def run_farm_checks(self) -> None:
        self.bot.farm_check_running = True
        hour = get_now().hour

        if hour == 11:
            await FarmChecker(self.bot).execute("7")
        elif hour == 17:
            await FarmChecker(self.bot).execute("6")
        else:
            for uid_start in GI_UID_PREFIXES:
                if uid_start in {"7", "6"}:
                    continue
                await FarmChecker(self.bot).execute(uid_start)

        self.bot.farm_check_running = False

    @tasks.loop(time=datetime.time(11, 0, 0, tzinfo=UTC_8))
    async def update_assets(self) -> None:
        await self.bot.update_assets()

    @tasks.loop(minutes=1)
    async def run_notes_check(self) -> None:
        await NotesChecker.execute(self.bot)

    @tasks.loop(minutes=1)
    async def run_send_embeds(self) -> None:
        await EmbedSender.execute(self.bot)

    @tasks.loop(time=[datetime.time(hour, 0, 0, tzinfo=UTC_8) for hour in range(0, 24, 1)])
    async def run_web_events_notify(self) -> None:
        await WebEventsNotify.execute(self.bot)

    @run_auto_tasks.before_loop
    @run_farm_checks.before_loop
    @update_assets.before_loop
    @run_notes_check.before_loop
    @run_send_embeds.before_loop
    @run_web_events_notify.before_loop
    async def before_loops(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Schedule(bot))
