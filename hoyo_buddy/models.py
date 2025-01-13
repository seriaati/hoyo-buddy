from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Literal

import aiohttp
import ambr.models
import enka
import genshin.models
from attr import dataclass
from discord import Locale
from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.l10n import LocaleStr

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


@dataclass(kw_only=True)
class ItemWithDescription:
    icon: str | None
    title: str | LocaleStr
    description: str | LocaleStr


@dataclass(kw_only=True)
class ItemWithTrailing:
    icon: str | None = None
    title: str | LocaleStr
    trailing: str | LocaleStr


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


class LightConeIcon:
    def __init__(self, id_: int) -> None:
        self._id = id_

    @property
    def image(self) -> str:
        return f"{STARRAIL_RES}/image/light_cone_portrait/{self._id}.png"

    @property
    def item(self) -> str:
        return f"https://api.yatta.top/hsr/assets/UI/equipment/medium/{self._id}.png"


@dataclass(kw_only=True)
class LightCone:
    id: int
    level: int
    superimpose: int
    name: str
    max_level: int
    rarity: int

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
    type: enka.hsr.RelicType


@dataclass(kw_only=True)
class Trace:
    anchor: str
    icon: str
    level: int


@dataclass(kw_only=True)
class Eidolon:
    icon: str
    unlocked: bool


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
    eidolons: list[Eidolon]
    element: str
    max_level: int
    rarity: int


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
    weapon_type: int


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


class AgentNameData(BaseModel):
    full_name: str
    short_name: str


class ZZZDrawData(BaseModel):
    name_data: dict[int, AgentNameData]
    agent_images: dict[int, str]
    disc_icons: dict[int, str]


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
    pos: int


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


class DeadlyAssault(genshin.models.DeadlyAssault):
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


@dataclass(kw_only=True)
class SingleBlock:
    icon: str
    icon_size: int = 204
    bg_color: str

    bottom_text: LocaleStr | str | None = None
    flair_text: LocaleStr | str | None = None


@dataclass(kw_only=True)
class DoubleBlock:
    icon1: str
    icon2: str
    bg_color: str
    icon_size: int = 204

    flair_text1: LocaleStr | str | None = None
    flair_text2: LocaleStr | str | None = None
    bottom_text: LocaleStr | str | None = None


@dataclass(kw_only=True)
class Dismissible:
    id: str

    title: LocaleStr | None = None
    description: LocaleStr
    image: str | None = None
    thumbnail: str | None = None
    footer: LocaleStr | None = None

    def to_embed(self, locale: Locale) -> DefaultEmbed:
        return (
            DefaultEmbed(
                locale,
                title=self.title or LocaleStr(key="dismissible_default_title"),
                description=self.description,
            )
            .set_image(url=self.image)
            .set_thumbnail(url=self.thumbnail)
            .set_footer(text=self.footer or LocaleStr(key="dismissible_default_footer"))
        )
