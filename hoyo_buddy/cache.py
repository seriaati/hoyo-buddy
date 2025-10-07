from __future__ import annotations

import io
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import orjson
import redis
from aiocache.serializers import BaseSerializer
from loguru import logger
from PIL import Image

from hoyo_buddy.config import CONFIG

IMAGE_CACHE_TTL = 3600


class OrjsonSerializer(BaseSerializer):
    DEFAULT_ENCODING = "utf-8"

    def dumps(self, value: Any) -> str:
        return orjson.dumps(value).decode()

    def loads(self, value: str | None) -> Any:
        if value is None:
            return None
        return orjson.loads(value.encode())


class RedisImageCache:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: redis.ConnectionPool | None = None
        self._bg_executor: ThreadPoolExecutor | None = None

    @property
    def redis(self) -> redis.ConnectionPool:
        if self._redis is None:
            msg = "Redis connection pool is not initialized. Call start() first."
            raise RuntimeError(msg)
        return self._redis

    @property
    def bg_executor(self) -> ThreadPoolExecutor:
        if self._bg_executor is None:
            msg = "Background executor is not initialized. Call start() first."
            raise RuntimeError(msg)
        return self._bg_executor

    def set(self, key: str, image: Image.Image) -> None:
        try:
            with redis.Redis(connection_pool=self.redis) as r, io.BytesIO() as output:
                image.save(output, format="PNG")
                r.setex(key, IMAGE_CACHE_TTL, output.getvalue())
        except redis.RedisError as e:
            logger.error(f"Redis error while setting image {key}: {e}")

    def set_background(self, key: str, image: Image.Image) -> None:
        self.bg_executor.submit(self.set, key, image.copy())

    def get(self, key: str) -> Image.Image | None:
        try:
            with redis.Redis(connection_pool=self.redis) as r:
                image_data = r.get(key)
                if image_data is None:
                    return None
        except redis.RedisError as e:
            logger.error(f"Redis error while getting image {key}: {e}")
            return None
        else:
            return Image.open(io.BytesIO(image_data))  # pyright: ignore[reportArgumentType]

    def start(self) -> None:
        logger.info(f"Process {os.getpid()} connected to Redis")
        self._redis = redis.ConnectionPool.from_url(self._redis_url)
        self._bg_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="RedisCacheWorker")

    def disconnect(self) -> None:
        self.bg_executor.shutdown(wait=True, cancel_futures=True)
        self.redis.disconnect()
        logger.info(f"Process {os.getpid()} disconnected from Redis")


image_cache = RedisImageCache(redis_url=CONFIG.redis_url) if CONFIG.redis_url else None
