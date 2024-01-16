import logging
from typing import TYPE_CHECKING

from tortoise import Tortoise

from .config import DB_CONFIG

if TYPE_CHECKING:
    from types import TracebackType

LOGGER_ = logging.getLogger(__name__)

__all__ = ("Database",)


class Database:
    async def __aenter__(self) -> None:
        await Tortoise.init(config=DB_CONFIG)
        LOGGER_.info("Connected to database")
        await Tortoise.generate_schemas()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: "TracebackType | None",
    ) -> None:
        await Tortoise.close_connections()
