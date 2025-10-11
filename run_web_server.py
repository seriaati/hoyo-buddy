from __future__ import annotations

import asyncio

from hoyo_buddy.config import CONFIG
from hoyo_buddy.db.pgsql import Database
from hoyo_buddy.l10n import translator
from hoyo_buddy.utils import setup_async_event_loop, setup_logging, setup_sentry, wrap_task_factory
from hoyo_buddy.web_server.server import GeetestWebServer


async def main() -> None:
    if CONFIG.web_server_port is None:
        msg = "Web server port is not configured in the settings."
        raise RuntimeError(msg)

    wrap_task_factory()
    setup_logging("logs/web_server.log")
    setup_async_event_loop()
    setup_sentry(CONFIG.web_server_sentry_dsn)

    async with Database(), translator:
        server = GeetestWebServer()
        await server.run(port=CONFIG.web_server_port)


if __name__ == "__main__":
    try:
        import uvloop  # pyright: ignore[reportMissingImports]
    except ImportError:
        asyncio.run(main())
    else:
        uvloop.run(main())
