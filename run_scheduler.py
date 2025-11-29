from __future__ import annotations

import asyncio

import aiohttp

from hoyo_buddy.config import CONFIG
from hoyo_buddy.db.pgsql import Database
from hoyo_buddy.l10n import translator
from hoyo_buddy.scheduler.main import Scheduler
from hoyo_buddy.utils import setup_async_event_loop, setup_logging, setup_sentry, wrap_task_factory


async def main() -> None:
    wrap_task_factory()
    setup_logging("logs/scheduler.log")
    setup_async_event_loop()
    setup_sentry(CONFIG.scheduler_sentry_dsn)

    async with Database(), translator, aiohttp.ClientSession() as session:
        scheduler = Scheduler(session)
        scheduler.start()

        try:
            while True:  # noqa: ASYNC110
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
