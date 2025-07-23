from __future__ import annotations

import asyncio

from hoyo_buddy.config import CONFIG
from hoyo_buddy.db.pgsql import Database
from hoyo_buddy.l10n import translator
from hoyo_buddy.utils import entry_point, wrap_task_factory
from hoyo_buddy.web_server.server import GeetestWebServer


async def main() -> None:
    if CONFIG.web_server_port is None:
        msg = "Web server port is not configured in the settings."
        raise RuntimeError(msg)

    wrap_task_factory()

    async with Database(), translator:
        server = GeetestWebServer()
        await server.run(port=CONFIG.web_server_port)


if __name__ == "__main__":
    entry_point("logs/web_server.log")
    asyncio.run(main())
