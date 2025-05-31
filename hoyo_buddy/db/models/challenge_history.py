# pyright: reportAssignmentType=false
from __future__ import annotations

import pickle
from typing import TYPE_CHECKING, Any, cast

import genshin
from loguru import logger
from tortoise import fields
from tortoise.exceptions import IntegrityError

from hoyo_buddy.constants import UTC_8
from hoyo_buddy.enums import ChallengeType

from .base import BaseModel

if TYPE_CHECKING:
    from collections.abc import Mapping

    from hoyo_buddy.types import Challenge, ChallengeWithLang


class ChallengeHistory(BaseModel):
    uid = fields.BigIntField(index=True)
    season_id = fields.IntField()
    name: fields.Field[str | None] = fields.CharField(max_length=64, null=True)
    challenge_type = fields.CharEnumField(ChallengeType, max_length=32)
    data: fields.Field[bytes | None] = fields.BinaryField(null=True)
    start_time = fields.DatetimeField()
    end_time = fields.DatetimeField()
    lang: fields.Field[str | None] = fields.CharField(max_length=5, null=True)
    json_data: fields.Field[dict[str, Any] | None] = fields.JSONField(null=True)

    class Meta:
        unique_together = ("uid", "season_id", "challenge_type")
        ordering = ("-end_time",)

    @property
    def duration_str(self) -> str:
        start_time = self.start_time.astimezone(UTC_8)
        end_time = self.end_time.astimezone(UTC_8)
        return f"{start_time:%Y-%m-%d} ~ {end_time:%Y-%m-%d}"

    @property
    def parsed_data(self) -> ChallengeWithLang:
        """Parsed challenge data from binary pickled data."""
        if self.json_data is None:
            if self.data is None:
                # This shouldn't happen, data could be None because of migration to use json_data
                msg = "Both json_data and data are None in ChallengeHistory"
                raise ValueError(msg)
            challenge = pickle.loads(self.data)
        else:
            challenge = self.load_data(self.json_data, challenge_type=self.challenge_type)

        lang = getattr(challenge, "lang", None)
        if lang is None:
            # NOTE: Backward compatibility, old data has lang attr, new data doesn't
            challenge.__dict__["lang"] = self.lang
        return cast("ChallengeWithLang", challenge)

    @classmethod
    def load_data(cls, raw: Mapping[str, Any], *, challenge_type: ChallengeType) -> Challenge:
        if challenge_type is ChallengeType.SPIRAL_ABYSS:
            return genshin.models.SpiralAbyss(**raw)
        if challenge_type is ChallengeType.IMG_THEATER:
            return genshin.models.ImgTheaterData(**raw)
        if challenge_type is ChallengeType.SHIYU_DEFENSE:
            return genshin.models.ShiyuDefense(**raw)
        if challenge_type is ChallengeType.ASSAULT:
            return genshin.models.DeadlyAssault(**raw)
        if challenge_type is ChallengeType.APC_SHADOW:
            return genshin.models.StarRailAPCShadow(**raw)
        if challenge_type is ChallengeType.MOC:
            return genshin.models.StarRailChallenge(**raw)
        if challenge_type is ChallengeType.PURE_FICTION:
            return genshin.models.StarRailPureFiction(**raw)

    @classmethod
    async def add_data(
        cls,
        *,
        uid: int,
        challenge_type: ChallengeType,
        season_id: int,
        raw: Mapping[str, Any],
        lang: str,
    ) -> None:
        data = cls.load_data(raw, challenge_type=challenge_type)

        if isinstance(data, genshin.models.SpiralAbyss | genshin.models.DeadlyAssault):
            start_time = data.start_time
            end_time = data.end_time
            name = None
        elif isinstance(data, genshin.models.ImgTheaterData):
            start_time = data.schedule.start_datetime
            end_time = data.schedule.end_datetime
            name = None
        elif isinstance(data, genshin.models.ShiyuDefense):
            start_time = data.begin_time
            end_time = data.end_time
            name = None
        else:
            season = next((season for season in data.seasons if season.id == season_id), None)
            if season is None:
                logger.error(f"Cannot find season with id {season_id} in add_data")
                return
            start_time = season.begin_time.datetime
            end_time = season.end_time.datetime
            name = season.name

        try:
            await cls.create(
                uid=uid,
                season_id=season_id,
                challenge_type=challenge_type,
                start_time=start_time,
                end_time=end_time,
                name=name,
                lang=lang,
                json_data=raw,
            )
        except IntegrityError:
            await cls.filter(uid=uid, season_id=season_id, challenge_type=challenge_type).update(
                name=name, lang=lang, json_data=raw
            )
