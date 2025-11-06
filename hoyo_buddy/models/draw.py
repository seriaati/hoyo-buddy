from __future__ import annotations

from typing import TYPE_CHECKING

from attr import dataclass
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import asyncio
    import concurrent.futures

    import aiohttp

    from hoyo_buddy.enums import Locale
    from hoyo_buddy.l10n import LocaleStr

__all__ = (
    "AgentNameData",
    "DoubleBlock",
    "DrawInput",
    "DynamicBKInput",
    "GICardData",
    "HSRCardData",
    "ItemWithDescription",
    "ItemWithTrailing",
    "SingleBlock",
    "TopPadding",
    "ZZZDrawData",
    "ZZZTemp1CardData",
    "ZZZTemp2CardData",
)


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
    executor: concurrent.futures.Executor
    loop: asyncio.AbstractEventLoop


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


class AgentNameData(BaseModel):
    full_name: str
    short_name: str


class ZZZDrawData(BaseModel):
    name_data: dict[int, AgentNameData]
    agent_images: dict[int, str]
    disc_icons: dict[int, str]


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


class ZZZTemp1CardData(BaseModel):
    image_x: int
    image_y: int
    image_w: int
    image_h: int

    level_x: int
    level_y: int

    color: str
    name_x: int | None = None
    name_y: int | None = None

    level_stroke: bool
    level_flip: bool
    flip: bool
    zzz_text: bool
    full_name: bool


class ZZZTemp2CardData(ZZZTemp1CardData):
    color: str | None = None
    full_name: bool = False


class GICardData(BaseModel):
    arts: list[str]


class HSRCardData(BaseModel):
    arts: list[str] = Field(default_factory=list)
    primary: str
    primary_dark: str | None = Field(default=None, alias="primary-dark")
