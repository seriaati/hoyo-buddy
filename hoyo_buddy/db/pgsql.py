from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from tortoise import Tortoise

from .config import DB_CONFIG

if TYPE_CHECKING:
    from types import TracebackType


__all__ = ("Database",)


class Database:
    async def __aenter__(self) -> None:
        await Tortoise.init(config=DB_CONFIG)
        logger.info("Connected to database")
        await Tortoise.generate_schemas()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await Tortoise.close_connections()
