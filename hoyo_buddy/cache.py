import io
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import orjson
import redis
import sentry_sdk
from aiocache.serializers import BaseSerializer
from loguru import logger
from PIL import Image
from redis.backoff import ExponentialBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

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

    def _ensure_connected(self) -> None:
        if self._redis is None or self._bg_executor is None:
            logger.debug("Redis connection pool is not initialized. Connecting...")
            self.connect()

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

    def _handle_error(self, op: str, key: str, e: RedisError) -> None:
        # A cache failure is non-critical: degrade like a cache miss instead of raising
        # to Sentry as an error. The scope fingerprint is a safety net so that, should
        # these ever be captured, they collapse into a single issue instead of one per key.
        with sentry_sdk.new_scope() as scope:
            scope.fingerprint = ["redis-cache-error"]
            scope.set_tag("cache_op", op)
            scope.set_extra("image_path", key)
            logger.debug(f"Redis cache error during {op}: {e}")

    def set(self, key: str, image: Image.Image) -> None:
        try:
            self._ensure_connected()
            with redis.Redis(connection_pool=self.redis) as r, io.BytesIO() as output:
                image.save(output, format="PNG")
                r.setex(key, IMAGE_CACHE_TTL, output.getvalue())
        except redis.BusyLoadingError:
            pass
        except RedisError as e:
            self._handle_error("set", key, e)

    def set_background(self, key: str, image: Image.Image) -> None:
        self._ensure_connected()
        self.bg_executor.submit(self.set, key, image.copy())

    def get(self, key: str) -> Image.Image | None:
        try:
            self._ensure_connected()
            with redis.Redis(connection_pool=self.redis) as r:
                image_data = r.get(key)
                if image_data is None:
                    return None
        except redis.BusyLoadingError:
            return None
        except RedisError as e:
            self._handle_error("get", key, e)
            return None
        else:
            return Image.open(io.BytesIO(image_data))  # pyright: ignore[reportArgumentType]

    def connect(self) -> None:
        if self._redis is not None and self._bg_executor is not None:
            return
        logger.info(f"Image cache in {os.getpid()} connected to Redis")
        self._redis = redis.ConnectionPool.from_url(
            self._redis_url,
            health_check_interval=30,
            socket_keepalive=True,
            retry_on_error=[redis.ConnectionError, redis.TimeoutError],
            retry=Retry(ExponentialBackoff(), 3),
        )
        self._bg_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="RedisCacheWorker")

    def disconnect(self) -> None:
        if self._bg_executor is not None:
            self._bg_executor.shutdown(wait=True, cancel_futures=True)
            self._bg_executor = None
        if self._redis is not None:
            self._redis.disconnect()
            self._redis = None
        logger.info(f"Image cache in {os.getpid()} disconnected from Redis")


image_cache = RedisImageCache(redis_url=CONFIG.redis_url) if CONFIG.redis_url else None
