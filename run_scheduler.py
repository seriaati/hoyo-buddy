from __future__ import annotations

import asyncio

import aiohttp

from hoyo_buddy.db.pgsql import Database
from hoyo_buddy.l10n import translator
from hoyo_buddy.scheduler.main import Scheduler
from hoyo_buddy.utils import entry_point, wrap_task_factory


async def main() -> None:
    wrap_task_factory()

    async with Database(), translator, aiohttp.ClientSession() as session:
        scheduler = Scheduler(session)
        scheduler.start()

        try:
            while True:  # noqa: ASYNC110
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            scheduler.shutdown()


if __name__ == "__main__":
    entry_point("logs/scheduler.log")
    asyncio.run(main())
