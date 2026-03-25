import asyncio
import contextlib

import uvicorn

from hoyo_buddy.config import CONFIG
from hoyo_buddy.l10n import translator
from hoyo_buddy.utils import setup_async_event_loop, setup_logging, setup_sentry, wrap_task_factory
from hoyo_buddy.web_app.api.app import app


async def main() -> None:
    if CONFIG.web_app_port is None:
        msg = "Web app port is not configured in settings."
        raise RuntimeError(msg)

    wrap_task_factory()
    setup_logging("logs/web_app.log")
    setup_async_event_loop()
    setup_sentry(CONFIG.web_app_sentry_dsn)
    await translator.load()

    config = uvicorn.Config(
        app, host="localhost", port=CONFIG.web_app_port, log_config=None, log_level=None
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
