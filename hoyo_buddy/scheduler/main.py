from __future__ import annotations

import asyncio
import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from hoyo_buddy.db.models.hoyo_account import HoyoAccount
from hoyo_buddy.hoyo.auto_tasks.auto_mimo import AutoMimoBuy, AutoMimoDraw, AutoMimoTask
from hoyo_buddy.hoyo.auto_tasks.auto_redeem import AutoRedeem
from hoyo_buddy.hoyo.auto_tasks.daily_checkin import DailyCheckin
from hoyo_buddy.utils import get_now

scheduler = AsyncIOScheduler()


async def reset_mimo_all_claimed_time() -> None:
    utc_now = get_now(datetime.UTC)
    await (
        HoyoAccount.filter(mimo_all_claimed_time__isnull=False)
        .exclude(mimo_all_claimed_time__day=utc_now.day)
        .update(mimo_all_claimed_time=None)
    )


# Run every 10 minutes
@scheduler.scheduled_job("interval", minutes=10)
async def run_auto_tasks() -> None:
    # Mimo
    await reset_mimo_all_claimed_time()
    asyncio.create_task(AutoMimoTask.execute())
    asyncio.create_task(AutoMimoBuy.execute())
    asyncio.create_task(AutoMimoDraw.execute())

    # Redeem
    asyncio.create_task(AutoRedeem.execute())

    # Check-in
    asyncio.create_task(DailyCheckin.execute())
