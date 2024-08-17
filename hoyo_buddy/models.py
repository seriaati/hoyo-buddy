from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import aiohttp
import ambr.models
from attr import dataclass
from discord import Locale
from genshin.models import StarRailPath
from pydantic import BaseModel, field_validator

from .constants import STARRAIL_RES

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


class LoginNotifPayload(BaseModel):
    user_id: int
    guild_id: int | None = None
    channel_id: int
    message_id: int | None = None
    gt_version: int
    api_server: str

    @classmethod
    def parse_from_request(cls, query: Mapping[str, str]) -> LoginNotifPayload:
        try:
            return cls(
                user_id=int(query["user_id"]),
                guild_id=int(query["guild_id"]) if "guild_id" in query else None,
                channel_id=int(query["channel_id"]),
                message_id=int(query["message_id"]) if "message_id" in query else None,
                gt_version=int(query["gt_version"]),
                api_server=query["api_server"],
            )
        except KeyError as e:
            msg = f"Missing query parameter: {e}"
            raise ValueError(msg) from e

    def to_query_string(self) -> str:
        return "&".join(f"{k}={v}" for k, v in self.model_dump().items() if v is not None)


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
    executor: concurrent.futures.ProcessPoolExecutor
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
        self.translator = args.translator
        self.search_autocomplete = args.search
        self.schedule = args.schedule


class UnownedCharacter(BaseModel):
    id: str
    element: str
    rarity: int
    path: StarRailPath = StarRailPath.ABUNDANCE
    level: int = 0
    friendship: int = 0
    constellation: int = 0
    rank: int = 0

    @field_validator("element", mode="before")
    @classmethod
    def __validate_element(cls, v: str) -> str:
        if v.lower() == "thunder":
            return "lightning"
        return v.lower()


class AgentNameData(NamedTuple):
    full_name: str
    short_name: str


class ZZZDrawData(NamedTuple):
    name_data: dict[str, AgentNameData]
    agent_images: dict[str, str]
    disc_icons: dict[str, str]
