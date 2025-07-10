from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from hoyo_buddy.db.models.hoyo_account import HoyoAccount
from hoyo_buddy.hoyo.auto_tasks.auto_mimo import AutoMimoBuy, AutoMimoDraw, AutoMimoTask
from hoyo_buddy.hoyo.auto_tasks.auto_redeem import AutoRedeem
from hoyo_buddy.hoyo.auto_tasks.daily_checkin import DailyCheckin
from hoyo_buddy.utils import get_now

if TYPE_CHECKING:
    import aiohttp

INTERVAL_MIN = 10


class Scheduler:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.session = session

    @staticmethod
    async def reset_mimo_all_claimed_time() -> None:
        utc_now = get_now(datetime.UTC)
        await (
            HoyoAccount.filter(mimo_all_claimed_time__isnull=False)
            .exclude(mimo_all_claimed_time__day=utc_now.day)
            .update(mimo_all_claimed_time=None)
        )

    async def run_auto_tasks(self) -> None:
        # Mimo
        await self.reset_mimo_all_claimed_time()
        asyncio.create_task(AutoMimoTask.execute())
        asyncio.create_task(AutoMimoBuy.execute())
        asyncio.create_task(AutoMimoDraw.execute())

        # Redeem
        asyncio.create_task(AutoRedeem.execute(self.session))

        # Check-in
        asyncio.create_task(DailyCheckin.execute())

    def start(self) -> None:
        self.scheduler.add_job(
            self.run_auto_tasks,
            "interval",
            minutes=INTERVAL_MIN,
            id="auto_tasks",
            next_run_time=get_now(datetime.UTC),
        )
        self.scheduler.start()

    def shutdown(self) -> None:
        self.scheduler.shutdown()
