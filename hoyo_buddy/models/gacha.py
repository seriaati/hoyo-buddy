from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Self

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from hoyo_buddy.constants import MW_EVENT_BANNER_TYPES

if TYPE_CHECKING:
    from pydantic import ValidationInfo

__all__ = (
    "SRGFRecord",
    "StarDBRecord",
    "StarRailStationRecord",
    "StarwardZZZRecord",
    "UIGFGameData",
    "UIGFHk4eRecord",
    "UIGFHk4eUgcRecord",
    "UIGFHkrpgRecord",
    "UIGFInfo",
    "UIGFNapRecord",
    "UIGFRecord",
    "UIGFv4Record",
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
    banner_type: int = Field(validation_alias=AliasChoices("uigf_gacha_type", "gacha_type"))
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


class UIGFInfo(BaseModel):
    export_timestamp: int
    export_app: str
    export_app_version: str
    version: str


class UIGFv4Record(BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: int
    item_id: int
    banner_type: int
    rarity: int = Field(alias="rank_type")
    time: datetime.datetime
    name: str | None = None
    item_type: str | None = None
    count: str | None = None

    @property
    def banner_id(self) -> int | None:
        return None

    @field_serializer("id", "item_id", "banner_type", "rarity")
    def __serialize_int(self, value: int) -> str:
        return str(value)

    @field_serializer("time")
    def __serialize_time(self, value: datetime.datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


class UIGFHk4eRecord(UIGFv4Record):
    banner_type: int = Field(alias="uigf_gacha_type")
    gacha_type: int

    @field_serializer("gacha_type")
    def __serialize_gacha_type(self, value: int) -> str:
        return str(value)


class UIGFHkrpgRecord(UIGFv4Record):
    banner_type: int = Field(alias="gacha_type")
    gacha_id: str

    @property
    def banner_id(self) -> int | None:
        return int(self.gacha_id) if self.gacha_id else None


class UIGFNapRecord(UIGFv4Record):
    banner_type: int = Field(alias="gacha_type")
    gacha_id: str | None = None

    @property
    def banner_id(self) -> int | None:
        return int(self.gacha_id) if self.gacha_id else None


class UIGFHk4eUgcRecord(UIGFv4Record):
    banner_type: int = Field(alias="op_gacha_type")
    schedule_id: str
    item_name: str

    @property
    def banner_id(self) -> int:
        return int(self.schedule_id)

    @field_validator("banner_type")
    @classmethod
    def __unify_banner_type(cls, value: int) -> int:
        return 2000 if value in MW_EVENT_BANNER_TYPES else value


class UIGFGameData[RecordT: UIGFv4Record](BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    uid: int
    timezone: int
    lang: str | None = None
    records: list[RecordT] = Field(alias="list")

    @model_validator(mode="after")
    def __add_timezone(self) -> Self:
        tz = datetime.timezone(datetime.timedelta(hours=self.timezone))
        for record in self.records:
            record.time = record.time.replace(tzinfo=tz)
        return self


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


class HSRBanner(BaseModel):
    id: int
    five_stars: list[int] = Field(alias="rateup")
    four_stars: list[int] = Field(alias="rateup4")
    start_at: datetime.datetime = Field(alias="start_time")
    end_at: datetime.datetime = Field(alias="end_time")

    @field_validator("five_stars", mode="before")
    @classmethod
    def __parse_five_stars(cls, v: int) -> list[int]:
        return [v]


class ZZZBanner(BaseModel):
    id: int
    five_stars: list[int] = Field(alias="rateupS")
    four_stars: list[int] = Field(alias="rateupA")
    start_at: datetime.datetime = Field(alias="start")
    end_at: datetime.datetime = Field(alias="end")


class GIBanner(BaseModel):
    id: int
    five_stars: list[str] = Field(default_factory=list, alias="featured")
    four_stars: list[str] = Field(default_factory=list, alias="featuredRare")
    start_at: datetime.datetime = Field(alias="start")
    end_at: datetime.datetime = Field(alias="end")

    def get_five_star_item_ids(self, item_names: dict[int, str]) -> list[int]:
        return [
            item_id
            for item_id, name in item_names.items()
            if name.replace(" ", "_").lower() in self.five_stars
        ]
