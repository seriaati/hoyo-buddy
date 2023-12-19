import logging
import sys
from types import TracebackType
from typing import Type

from redis import asyncio as aioredis
from yarl import URL

log = logging.getLogger(__name__)


class RedisPool:
    def __init__(self, uri: str, max_size: int = 30) -> None:
        self.uri = uri
        self.max_size = max_size
        self.pool = None

    async def __aenter__(self) -> aioredis.ConnectionPool:
        return await self.create_pool()

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ):
        if self.pool is not None:
            await self.pool.disconnect()
            log.info("Disconnected from redis successfully.")

    async def create_pool(self) -> aioredis.ConnectionPool:
        complete_uri = URL(self.uri) % {"decode_responses": "True", "protocol": 2}
        self.pool = aioredis.ConnectionPool(max_connections=self.max_size).from_url(
            str(complete_uri)
        )
        log.info("Connected to redis successfully.")
        if "--flush-cache" in sys.argv:
            async with aioredis.Redis(connection_pool=self.pool) as redis:
                await redis.flushdb()
                log.info("Flushed redis cache.")
        return self.pool
