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
        logger.info(f"Process {os.getpid()} creating redis connection pool...")
        self.redis = redis.ConnectionPool.from_url(redis_url)
        self.bg_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="RedisCacheWorker")

    def set(self, key: str, image: Image.Image) -> None:
        try:
            with redis.Redis(connection_pool=self.redis) as r, io.BytesIO() as output:
                image.save(output, format="PNG")
                r.set(key, output.getvalue())
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

    def disconnect(self) -> None:
        self.bg_executor.shutdown(wait=True, cancel_futures=True)
        self.redis.disconnect()
        logger.info(f"Process {os.getpid()} disconnected from Redis")


image_cache = RedisImageCache(redis_url=CONFIG.redis_url) if CONFIG.redis_url else None
