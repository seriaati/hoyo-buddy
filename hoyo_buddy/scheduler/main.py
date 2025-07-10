from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler

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

    def add_jobs(self) -> None:
        self.scheduler.add_job(
            AutoMimoTask.execute,
            "interval",
            minutes=INTERVAL_MIN,
            next_run_time=get_now(datetime.UTC),
        )
        self.scheduler.add_job(
            AutoMimoBuy.execute,
            "interval",
            minutes=INTERVAL_MIN,
            next_run_time=get_now(datetime.UTC),
        )
        self.scheduler.add_job(
            AutoMimoDraw.execute,
            "interval",
            minutes=INTERVAL_MIN,
            next_run_time=get_now(datetime.UTC),
        )
        self.scheduler.add_job(
            AutoRedeem.execute,
            "interval",
            args=(self.session,),
            minutes=INTERVAL_MIN,
            next_run_time=get_now(datetime.UTC),
        )
        self.scheduler.add_job(
            DailyCheckin.execute,
            "interval",
            minutes=INTERVAL_MIN,
            next_run_time=get_now(datetime.UTC),
        )

    def start(self) -> None:
        self.add_jobs()
        self.scheduler.start()

    def shutdown(self) -> None:
        self.scheduler.shutdown()
