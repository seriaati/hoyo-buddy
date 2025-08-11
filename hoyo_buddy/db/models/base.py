from __future__ import annotations

import asyncio
from typing import Any, ClassVar, Self

import orjson
import redis.asyncio as redis
from loguru import logger
from tortoise.models import Model

from hoyo_buddy.config import CONFIG


class BaseModel(Model):
    def __str__(self) -> str:
        return repr(self)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(f'{field}={getattr(self, field)!r}' for field in self._meta.db_fields if hasattr(self, field))})"

    class Meta:
        abstract = True


class CachedModel(BaseModel):
    _redis_pool: ClassVar[redis.ConnectionPool | None] = None
    _cache_ttl: ClassVar[int] = 3600
    _cache_prefix: ClassVar[str] = "cached_model"

    class Meta:
        abstract = True

    @classmethod
    async def _get_redis(cls) -> redis.Redis | None:
        """Get Redis connection from pool."""
        if not CONFIG.redis_url:
            return None

        if cls._redis_pool is None:
            try:
                cls._redis_pool = redis.ConnectionPool.from_url(
                    CONFIG.redis_url,
                    decode_responses=True,
                    retry_on_timeout=True,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                )
            except Exception as e:
                logger.error(f"Failed to create Redis connection pool: {e}")
                return None

        try:
            return redis.Redis(connection_pool=cls._redis_pool)
        except Exception as e:
            logger.error(f"Failed to get Redis connection: {e}")
            return None

    @classmethod
    def _get_cache_key(cls, pk: Any) -> str:
        """Generate cache key for instance."""
        return f"{cls._cache_prefix}:{cls.__name__}:{pk}"

    def serialize(self) -> dict[str, Any]:
        """Serialize model instance for caching."""
        return {
            field: getattr(self, field) for field in self._meta.db_fields if hasattr(self, field)
        }

    @classmethod
    def _deserialize(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Deserialize cached data for model creation."""
        return data

    async def _cache_set(self) -> None:
        """Cache this instance."""
        redis_conn = await self._get_redis()
        if not redis_conn:
            return

        try:
            cache_key = self._get_cache_key(self.pk)
            serialized_data = self.serialize()
            json_data = orjson.dumps(serialized_data).decode("utf-8")

            await redis_conn.setex(cache_key, self._cache_ttl, json_data)
            logger.debug(f"Cached {self.__class__.__name__} instance with key: {cache_key}")
        except Exception as e:
            logger.error(f"Failed to cache {self.__class__.__name__} instance: {e}")
        finally:
            await redis_conn.aclose()

    async def _cache_delete(self) -> None:
        """Delete this instance from cache."""
        redis_conn = await self._get_redis()
        if not redis_conn:
            return

        try:
            cache_key = self._get_cache_key(self.pk)
            await redis_conn.delete(cache_key)
            logger.debug(f"Deleted cache for {self.__class__.__name__} with key: {cache_key}")
        except Exception as e:
            logger.error(f"Failed to delete cache for {self.__class__.__name__} instance: {e}")
        finally:
            await redis_conn.aclose()

    @classmethod
    async def _cache_get(cls, pk: Any) -> dict[str, Any] | None:
        """Get instance data from cache."""
        redis_conn = await cls._get_redis()
        if not redis_conn:
            return None

        try:
            cache_key = cls._get_cache_key(pk)
            cached_data = await redis_conn.get(cache_key)

            if cached_data is None:
                logger.debug(f"Cache miss for {cls.__name__} with key: {cache_key}")
                return None

            logger.debug(f"Cache hit for {cls.__name__} with key: {cache_key}")
            return orjson.loads(cached_data)
        except Exception as e:
            logger.error(f"Failed to get cache for {cls.__name__} instance: {e}")
            return None
        finally:
            await redis_conn.aclose()

    @classmethod
    async def get_cached(cls, pk: Any, **kwargs: Any) -> Self:
        """Get instance with cache-aside pattern."""
        cached_data = await cls._cache_get(pk)
        if cached_data is not None:
            try:
                deserialized_data = cls._deserialize(cached_data)
                instance = cls._init_from_db(**deserialized_data)
            except Exception as e:
                logger.error(f"Failed to deserialize cached {cls.__name__}: {e}")
            else:
                return instance

        try:
            instance = await super().get(pk=pk, **kwargs)
            asyncio.create_task(instance._cache_set())
        except Exception as e:
            logger.error(f"Failed to get {cls.__name__} from database: {e}")
            raise
        else:
            return instance

    @classmethod
    async def get_or_none_cached(cls, pk: Any, **kwargs: Any) -> Self | None:
        """Get instance or None with cache-aside pattern."""
        cached_data = await cls._cache_get(pk)
        if cached_data is not None:
            try:
                deserialized_data = cls._deserialize(cached_data)
                instance = cls._init_from_db(**deserialized_data)
            except Exception as e:
                logger.error(f"Failed to deserialize cached {cls.__name__}: {e}")
            else:
                return instance

        try:
            instance = await super().get_or_none(pk=pk, **kwargs)
            if instance is not None:
                asyncio.create_task(instance._cache_set())
        except Exception as e:
            logger.error(f"Failed to get {cls.__name__} from database: {e}")
            raise
        else:
            return instance

    @classmethod
    async def get_or_create_cached(cls, **kwargs: Any) -> tuple[Self, bool]:
        """Get or create an instance with cache-aside pattern."""
        instance = await cls.get_or_none_cached(**kwargs)
        if instance is not None:
            return instance, False

        instance = await cls.create(**kwargs)
        asyncio.create_task(instance._cache_set())
        return instance, True

    async def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save to cache after database operation."""
        await super().save(*args, **kwargs)
        asyncio.create_task(self._cache_set())

    async def delete(self, *args: Any, **kwargs: Any) -> None:
        """Override delete to invalidate cache."""
        await self._cache_delete()
        await super().delete(*args, **kwargs)

    @classmethod
    async def close_redis_pool(cls) -> None:
        """Close Redis connection pool."""
        if cls._redis_pool is not None:
            await cls._redis_pool.aclose()
            cls._redis_pool = None
            logger.info("Redis connection pool closed")
