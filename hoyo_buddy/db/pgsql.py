import logging
from types import TracebackType
from typing import Type

from tortoise import Tortoise

from .config import DB_CONFIG

log = logging.getLogger(__name__)

__all__ = ("Database",)


class Database:
    async def __aenter__(self):
        await Tortoise.init(config=DB_CONFIG)
        log.info("Connected to database")
        await Tortoise.generate_schemas()

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ):
        await Tortoise.close_connections()
