from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Literal, NamedTuple

import aiohttp
import ambr.models
import enka
import genshin.models
from attr import dataclass
from discord import Locale
from pydantic import BaseModel, Field, ValidationInfo, field_validator

from .constants import STARRAIL_RES
from .enums import GeetestType, GenshinElement

if TYPE_CHECKING:
    import argparse
    import asyncio
    import concurrent.futures
    from collections.abc import Mapping


@dataclass(kw_only=True)
class Reward:
    name: str
    amount: int
    index: int
    claimed: bool
    icon: str


class GeetestCommandPayload(BaseModel):
    user_id: int

    guild_id: int | None = None
    message_id: int
    channel_id: int

    gt_version: int
    api_server: str
    gt_type: GeetestType
    account_id: int
    locale: str

    @classmethod
    def parse_from_request(cls, query: Mapping[str, str]) -> GeetestCommandPayload:
        return cls(
            user_id=int(query["user_id"]),
            guild_id=int(query["guild_id"]) if "guild_id" in query else None,
            channel_id=int(query["channel_id"]),
            message_id=int(query["message_id"]),
            gt_version=int(query["gt_version"]),
            api_server=query["api_server"],
            gt_type=GeetestType(query["gt_type"]),
            account_id=int(query["account_id"]),
            locale=query["locale"],
        )

    def to_query_string(self) -> str:
        return "&".join(f"{k}={v}" for k, v in self.model_dump().items() if v is not None)


class GeetestLoginPayload(BaseModel):
    user_id: int
    gt_version: int
    api_server: str = "api-na.geetest.com"

    @classmethod
    def parse_from_request(cls, query: Mapping[str, str]) -> GeetestLoginPayload:
        return cls(
            user_id=int(query["user_id"]),
            gt_version=int(query["gt_version"]),
            api_server=query["api_server"],
        )

    def to_query_string(self) -> str:
        return "&".join(f"{k}={v}" for k, v in self.model_dump().items())


class ItemWithDescription(BaseModel):
    icon: str | None
    title: str
    description: str


class ItemWithTrailing(BaseModel):
    icon: str | None
    title: str
    trailing: str


@dataclass(kw_only=True)
class DrawInput:
    dark_mode: bool
    locale: Locale
    session: aiohttp.ClientSession
    filename: str
    executor: concurrent.futures.ThreadPoolExecutor
    loop: asyncio.AbstractEventLoop


class FarmData:
    def __init__(self, domain: ambr.models.Domain) -> None:
        self.domain = domain
        self.characters: list[ambr.models.Character] = []
        self.weapons: list[ambr.models.Weapon] = []


@dataclass(kw_only=True)
class TopPadding:
    with_title: int
    without_title: int


@dataclass(kw_only=True)
class DynamicBKInput:
    top_padding: TopPadding | int
    left_padding: int
    right_padding: int
    bottom_padding: int
    card_height: int
    card_width: int
    card_x_padding: int
    card_y_padding: int
    card_num: int
    background_color: tuple[int, int, int]
    max_card_num: int | None = None
    draw_title: bool = True


@dataclass(kw_only=True)
class AbyssCharacter:
    level: int
    const: int
    icon: str


class LightConeIcon:
    def __init__(self, id_: int) -> None:
        self._id = id_

    @property
    def image(self) -> str:
        return f"{STARRAIL_RES}/image/light_cone_portrait/{self._id}.png"


@dataclass(kw_only=True)
class LightCone:
    id: int
    level: int
    superimpose: int
    name: str
    max_level: int

    @property
    def icon(self) -> LightConeIcon:
        return LightConeIcon(self.id)


@dataclass(kw_only=True)
class Stat:
    type: int
    icon: str
    formatted_value: str


@dataclass(kw_only=True)
class Relic:
    id: int
    level: int
    rarity: int
    icon: str
    main_stat: Stat
    sub_stats: list[Stat]


@dataclass(kw_only=True)
class Trace:
    anchor: str
    icon: str
    level: int


@dataclass(kw_only=True)
class HoyolabHSRCharacter:
    id: str
    name: str
    level: int
    eidolons_unlocked: int
    light_cone: LightCone | None = None
    relics: list[Relic]
    stats: list[Stat]
    traces: list[Trace]
    element: str
    max_level: int


class Config:
    def __init__(self, args: argparse.Namespace) -> None:
        self.sentry = args.sentry
        self.search_autocomplete = args.search
        self.schedule = args.schedule


class UnownedGICharacter(BaseModel):
    id: str
    element: str
    rarity: int
    level: int = 0
    friendship: int = 0
    constellation: int = 0


class UnownedHSRCharacter(BaseModel):
    id: int
    element: str
    rarity: int
    path: genshin.models.StarRailPath
    level: int = 0
    rank: int = 0

    @field_validator("element", mode="before")
    @classmethod
    def __transform_element_name(cls, v: str) -> str:
        if v.lower() == "thunder":
            return "lightning"
        return v.lower()


class UnownedZZZCharacter(BaseModel):
    id: int
    element: genshin.models.ZZZElementType
    rarity: Literal["S", "A"]
    level: int = 0
    specialty: genshin.models.ZZZSpecialty
    faction_name: str
    rank: int = 0
    banner_icon: str


class AgentNameData(NamedTuple):
    full_name: str
    short_name: str


class ZZZDrawData(NamedTuple):
    name_data: dict[str, AgentNameData]
    agent_images: dict[str, str]
    disc_icons: dict[str, str]


class HoyolabGIStat(BaseModel):
    type: enka.gi.FightPropType
    formatted_value: str


class HoyolabGIWeapon(BaseModel):
    name: str
    stats: list[HoyolabGIStat]
    icon: str
    refinement: int
    level: int
    max_level: int
    rarity: int


class HoyolabGIConst(BaseModel):
    icon: str
    unlocked: bool


class HoyolabGITalent(BaseModel):
    icon: str
    level: int
    id: int


class HoyolabGIArtifact(BaseModel):
    icon: str
    rarity: int
    level: int
    main_stat: HoyolabGIStat
    sub_stats: list[HoyolabGIStat]


class HoyolabGICharacterIcon(BaseModel):
    gacha: str


class HoyolabGICharacter(BaseModel):
    id: int
    name: str
    element: GenshinElement
    highest_dmg_bonus_stat: HoyolabGIStat
    stats: dict[enka.gi.FightPropType, HoyolabGIStat]
    rarity: int

    weapon: HoyolabGIWeapon
    constellations: list[HoyolabGIConst]
    talent_order: list[int]
    talents: list[HoyolabGITalent]
    artifacts: list[HoyolabGIArtifact]

    friendship_level: int
    level: int
    max_level: int
    icon: HoyolabGICharacterIcon


class ImgTheaterData(genshin.models.ImgTheaterData):
    lang: str


class StarRailChallenge(genshin.models.StarRailChallenge):
    lang: str


class SpiralAbyss(genshin.models.SpiralAbyss):
    lang: str


class StarRailPureFiction(genshin.models.StarRailPureFiction):
    lang: str


class StarRailAPCShadow(genshin.models.StarRailAPCShadow):
    lang: str


class ShiyuDefense(genshin.models.ShiyuDefense):
    lang: str


class StarRailStationRecord(BaseModel):
    id: int = Field(alias="uid")
    item_id: int = Field(alias="id")
    rarity: int
    time: datetime.datetime
    banner_type: int = Field(alias="type")


class ZZZRngMoeRecord(BaseModel):
    id: int = Field(alias="uid")
    item_id: int = Field(alias="id")
    rarity: int
    tz_hour: int
    time: datetime.datetime = Field(alias="timestamp")
    banner_type: int = Field(alias="gachaType")

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


class GWRecord(BaseModel):
    rarity: int = Field(alias="Rarity")
    id: int = Field(alias="ID")
    name: str = Field(alias="Name")
    time: datetime.datetime = Field(alias="Date")
    banner: int = Field(alias="Banner")

    @field_validator("time")
    @classmethod
    def __add_timezone(cls, value: datetime.datetime) -> datetime.datetime:
        return value.replace(tzinfo=datetime.UTC)

    @field_validator("banner", mode="before")
    @classmethod
    def __convert_banner(
        cls, value: Literal["Weapon", "Character", "Permanent", "Chronicled", "Novice"]
    ) -> int:
        return {
            "Weapon": 302,
            "Character": 301,
            "Permanent": 200,
            "Chronicled": 500,
            "Novice": 100,
        }[value]
