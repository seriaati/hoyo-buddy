from typing import Any, Dict, Optional, Self, Tuple

import genshin
import orjson
import redis.asyncio as redis
from discord import Locale
from tortoise import fields
from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.models import Model as TortoiseModel

from ..db import GAME_CONVERTER
from ..hoyo.client import GenshinClient
from . import Game

__all__ = (
    "User",
    "HoyoAccount",
    "AccountNotifSettings",
    "Settings",
)


class Model(TortoiseModel):
    @classmethod
    async def get_or_create(cls, **kwargs: Any) -> Tuple[Self, bool]:
        try:
            return await cls.get(**kwargs), False
        except DoesNotExist:
            return await cls.create(**kwargs), True

    @classmethod
    async def silent_create(cls, **kwargs: Any) -> Self | None:
        try:
            return await cls.create(find_from_cache_first=True, **kwargs)
        except IntegrityError:
            return None


class CacheModel(Model):
    @classmethod
    def from_json(cls, data: bytes) -> Self:
        return cls(**orjson.loads(data))

    @classmethod
    async def get(cls, pool: redis.ConnectionPool, **kwargs: Any) -> Self:  # skipcq: PYL-W0236
        instance = cls(**kwargs)
        cached = await instance.get_cache(pool)
        if cached:
            cached._saved_in_db = True  # skipcq: PYL-W0212
            return cached

        instance = await super().get(**kwargs)
        await instance.set_cache(pool)
        return instance

    @classmethod
    async def create(cls, pool: redis.ConnectionPool, **kwargs: Any) -> Self:
        instance = cls(**kwargs)
        for key, value in kwargs.items():
            setattr(instance, key, value)

        await instance.save(pool)
        await instance.set_cache(pool)
        return instance

    @classmethod
    async def get_or_create(cls, pool: redis.ConnectionPool, **kwargs: Any) -> Tuple[Self, bool]:
        try:
            return await cls.get(pool, **kwargs), False
        except DoesNotExist:
            return await cls.create(pool, **kwargs), True

    @classmethod
    async def silent_create(cls, pool: redis.ConnectionPool, **kwargs: Any) -> Self | None:
        try:
            return await cls.create(pool, **kwargs)
        except IntegrityError:
            return None

    @property
    def _key(self) -> str:
        raise NotImplementedError

    def to_json(self) -> bytes:
        return orjson.dumps(
            {
                key: value
                for key, value in self.__dict__.items()
                if key in self._meta.db_fields and value is not None  # skipcq: PYL-W0212
            }
        )

    def get_cache_key(self) -> str:
        return f"{self.__class__.__name__}:{self._key}"

    async def set_cache(self, pool: redis.ConnectionPool) -> None:
        async with redis.Redis.from_pool(pool) as r:
            await r.set(self.get_cache_key(), self.to_json(), ex=60 * 60)

    async def get_cache(self, pool: redis.ConnectionPool) -> Optional[Self]:
        async with redis.Redis.from_pool(pool) as r:
            data = await r.get(self.get_cache_key())
        if data:
            return self.from_json(data)
        return None

    async def save(self, pool: redis.ConnectionPool) -> None:
        await super().save()
        await self.set_cache(pool)


class User(CacheModel):
    id = fields.BigIntField(pk=True, index=True, generated=False)
    settings: fields.BackwardOneToOneRelation["Settings"]
    temp_data: Dict[str, Any] = fields.JSONField(default=dict)  # type: ignore
    accounts: fields.ReverseRelation["HoyoAccount"]

    @property
    def _key(self) -> str:
        return str(self.id)


class HoyoAccount(Model):
    uid = fields.IntField(index=True)
    username = fields.CharField(max_length=32)
    nickname: fields.Field[Optional[str]] = fields.CharField(max_length=32, null=True)  # type: ignore
    game = fields.CharEnumField(Game, max_length=32)
    cookies = fields.TextField()
    server = fields.CharField(max_length=32)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="accounts"
    )
    daily_checkin = fields.BooleanField(default=True)
    notif_settings: fields.BackwardOneToOneRelation["AccountNotifSettings"]

    class Meta:
        unique_together = ("uid", "game", "user")
        ordering = ["uid"]

    def __str__(self) -> str:
        if self.nickname:
            return f"{self.nickname} ({self.uid})"
        return f"{self.username} ({self.uid})"

    @property
    def client(self) -> GenshinClient:
        game: genshin.Game = GAME_CONVERTER[self.game]  # type: ignore
        return GenshinClient(self.cookies, game=game, uid=self.uid)


class AccountNotifSettings(Model):
    notify_on_checkin_failure = fields.BooleanField(default=True)
    notify_on_checkin_success = fields.BooleanField(default=True)
    account: fields.OneToOneRelation[HoyoAccount] = fields.OneToOneField(
        "models.HoyoAccount", related_name="notif_settings"
    )


class Settings(CacheModel):
    lang: fields.Field[Optional[str]] = fields.CharField(max_length=5, null=True)  # type: ignore
    dark_mode = fields.BooleanField(default=True)
    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User", related_name="settings"
    )

    @property
    def _key(self) -> str:
        return str(self.__dict__["user_id"])

    @property
    def locale(self) -> Optional[Locale]:
        return Locale(self.lang) if self.lang else None

    @classmethod
    async def get_locale(cls, user_id: int, pool: redis.ConnectionPool) -> Optional[Locale]:
        return (await cls.get(pool, user_id=user_id)).locale
