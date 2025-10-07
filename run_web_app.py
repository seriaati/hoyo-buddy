from __future__ import annotations

import asyncio
import contextlib

import fastapi
import flet as ft
import uvicorn

from hoyo_buddy.config import CONFIG
from hoyo_buddy.l10n import translator
from hoyo_buddy.utils import setup_async_event_loop, setup_logging, setup_sentry, wrap_task_factory
from hoyo_buddy.web_app.app import ClientStorage, WebApp


async def target(page: ft.Page) -> None:
    setattr(page, f"_{page.__class__.__name__}__client_storage", ClientStorage(page))
    app = WebApp(page)
    await app.initialize()


app = ft.app(
    target,
    view=None,
    assets_dir="hoyo_buddy/web_app/assets",
    use_color_emoji=True,
    export_asgi_app=True,
)


async def main() -> None:
    if CONFIG.web_app_port is None:
        msg = "Web app port is not configured in settings."
        raise RuntimeError(msg)

    wrap_task_factory()
    setup_logging("logs/web_app.log")
    setup_async_event_loop()
    setup_sentry(CONFIG.web_app_sentry_dsn)

    await translator.load()

    assert isinstance(app, fastapi.FastAPI)
    config = uvicorn.Config(app, port=CONFIG.web_app_port, log_config=None, log_level=None)
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt, asyncio.CancelledError, ImportError):
        try:
            import uvloop  # pyright: ignore[reportMissingImports]
        except ImportError:
            asyncio.run(main())
        else:
            uvloop.run(main())
