import logging
from types import TracebackType
from typing import Optional, Type

from tortoise import Tortoise

from .configs import DB_CONFIG

log = logging.getLogger(__name__)


class Database:
    async def __aenter__(self):
        await Tortoise.init(config=DB_CONFIG)
        log.info("Connected to database")
        await Tortoise.generate_schemas()

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ):
        await Tortoise.close_connections()
