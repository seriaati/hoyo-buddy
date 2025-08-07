from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

__all__ = (
    "SRGFRecord",
    "StarDBRecord",
    "StarRailStationRecord",
    "StarwardZZZRecord",
    "UIGFRecord",
    "ZZZRngMoeRecord",
)


class StarRailStationRecord(BaseModel):
    id: int = Field(alias="uid")
    item_id: int = Field(alias="id")
    rarity: int
    time: datetime.datetime
    banner_type: int = Field(alias="type")
    banner_id: int = Field(alias="banner")


class ZZZRngMoeRecord(BaseModel):
    id: int = Field(alias="uid")
    item_id: int = Field(alias="id")
    rarity: int
    tz_hour: int
    time: datetime.datetime = Field(alias="timestamp")
    banner_type: int = Field(alias="gachaType")
    banner_id: int = Field(alias="gacha")

    @field_validator("time")
    @classmethod
    def __add_timezone(cls, value: datetime.datetime, info: ValidationInfo) -> datetime.datetime:
        return value.replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=info.data["tz_hour"]))
        )

    @field_validator("banner_type")
    @classmethod
    def __transform_banner_type(cls, value: int) -> int:
        return value // 1000


class StarDBRecord(BaseModel):
    id: int
    item_id: int
    time: datetime.datetime = Field(alias="timestamp")
    banner_type: int

    @field_validator("banner_type")
    @classmethod
    def __unify_banner_type(cls, value: int) -> int:
        return 301 if value == 400 else value


class UIGFRecord(BaseModel):
    banner_type: int = Field(alias="uigf_gacha_type")
    item_id: int
    tz_hour: int = Field(alias="timezone")
    time: datetime.datetime
    id: int
    rarity: int = Field(alias="rank_type")

    @field_validator("time")
    @classmethod
    def __add_timezone(cls, value: datetime.datetime, info: ValidationInfo) -> datetime.datetime:
        return value.replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=info.data["tz_hour"]))
        )

    @model_validator(mode="before")
    @classmethod
    def __find_gacha_type(cls, values: dict[str, Any]) -> dict[str, Any]:
        banner_type = values.get("uigf_gacha_type")
        if banner_type is None:
            values["uigf_gacha_type"] = values["gacha_type"]
        return values


class SRGFRecord(BaseModel):
    banner_type: int = Field(alias="gacha_type")
    item_id: int
    tz_hour: int = Field(alias="timezone")
    time: datetime.datetime
    id: int
    rarity: int = Field(alias="rank_type")

    @field_validator("time")
    @classmethod
    def __add_timezone(cls, value: datetime.datetime, info: ValidationInfo) -> datetime.datetime:
        return value.replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=info.data["tz_hour"]))
        )


class StarwardZZZRecord(BaseModel):
    id: int
    banner_type: int = Field(alias="gacha_type")
    rarity: int = Field(alias="rank_type")
    tz_hour: int
    time: datetime.datetime
    item_id: int

    @field_validator("time")
    @classmethod
    def __add_timezone(cls, value: datetime.datetime, info: ValidationInfo) -> datetime.datetime:
        return value.replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=info.data["tz_hour"]))
        )
