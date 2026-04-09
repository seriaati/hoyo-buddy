import asyncio
import contextlib

import uvicorn

from hoyo_buddy.api.app import app
from hoyo_buddy.config import CONFIG
from hoyo_buddy.l10n import translator
from hoyo_buddy.utils import setup_async_event_loop, setup_logging, setup_sentry, wrap_task_factory


async def main() -> None:
    if CONFIG.api_port is None:
        msg = "API port is not configured in settings."
        raise RuntimeError(msg)

    wrap_task_factory()
    setup_logging("logs/api.log")
    setup_async_event_loop()
    setup_sentry(CONFIG.api_sentry_dsn)
    await translator.load()

    config = uvicorn.Config(
        app, host="localhost", port=CONFIG.api_port, log_config=None, log_level=None
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt, asyncio.CancelledError):
        try:
            import uvloop
        except ImportError:
            asyncio.run(main())
        else:
            uvloop.run(main())
