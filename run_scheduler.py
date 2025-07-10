from __future__ import annotations

import asyncio

import aiohttp

from hoyo_buddy.scheduler.main import Scheduler


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        scheduler = Scheduler(session)
        try:
            scheduler.start()
        except KeyboardInterrupt:
            scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
