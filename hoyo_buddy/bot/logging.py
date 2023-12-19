import contextlib
import logging
import logging.handlers

import discord

__all__ = ("setup_logging",)


@contextlib.contextmanager
def setup_logging(env: str):
    log = logging.getLogger()

    try:
        discord.utils.setup_logging()

        max_bytes = 32 * 1024 * 1024
        logging.getLogger("discord").setLevel(logging.INFO)
        logging.getLogger("discord.http").setLevel(logging.WARNING)

        if env == "prod":
            log.setLevel(logging.INFO)
        else:
            log.setLevel(logging.DEBUG)

        handler = logging.handlers.RotatingFileHandler(
            filename="hoyo_buddy.log",
            encoding="utf-8",
            mode="w",
            maxBytes=max_bytes,
            backupCount=5,
        )
        dt_fmt = "%Y-%m-%d %H:%M:%S"
        fmt = logging.Formatter("[{asctime}] [{levelname:<7}] {name}: {message}", dt_fmt, style="{")
        handler.setFormatter(fmt)
        log.addHandler(handler)

        yield
    finally:
        handlers = log.handlers[:]
        for handler in handlers:
            handler.close()
            log.removeHandler(handler)
