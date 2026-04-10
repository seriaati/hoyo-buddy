from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from hoyo_buddy.enums import Platform
from hoyo_buddy.l10n import BANNER_TYPE_NAMES

__all__ = [
    "AccountInfo",
    "AccountSubmitRequest",
    "AuthCallbackRequest",
    "AuthURLResponse",
    "BannerTypeInfo",
    "BannerTypesResponse",
    "DevToolsCookiesRequest",
    "DeviceInfoRequest",
    "EmailPasswordRequest",
    "EmailVerifyRequest",
    "ErrorResponse",
    "FinishAccountsResponse",
    "GachaItem",
    "GachaLogResponse",
    "GachaParams",
    "GachaStatsResponse",
    "GeetestCommandRequest",
    "LoginFlowResponse",
    "MobileRequest",
    "ModAppRequest",
    "OTPVerifyRequest",
    "Params",
    "QRCodeResponse",
    "QRCodeStatusResponse",
    "RawCookiesRequest",
    "UserResponse",
]


# ── Auth ──────────────────────────────────────────────────────────────────────


class AuthURLResponse(BaseModel):
    url: str


class UserResponse(BaseModel):
    id: str
    username: str
    avatar_url: str


class AuthCallbackRequest(BaseModel):
    code: str
    state: str


# ── Login flow ────────────────────────────────────────────────────────────────


class EmailPasswordRequest(BaseModel):
    email: str
    password: str


class DevToolsCookiesRequest(BaseModel):
    ltuid_v2: str
    account_id_v2: str
    ltoken_v2: str
    ltmid_v2: str
    account_mid_v2: str


class RawCookiesRequest(BaseModel):
    cookies: str


class ModAppRequest(BaseModel):
    login_details: str


class MobileRequest(BaseModel):
    mobile: str


class OTPVerifyRequest(BaseModel):
    code: str


class EmailVerifyRequest(BaseModel):
    code: str


class DeviceInfoRequest(BaseModel):
    device_info: str
    aaid: str | None = None


class LoginFlowResponse(BaseModel):
    next_step: Literal["geetest", "email_verify", "verify_otp", "finish", "done"]
    gt_version: int | None = None
    api_server: str | None = None
    message: str | None = None
    mmt: dict | None = None


class QRCodeResponse(BaseModel):
    ticket: str
    image_base64: str


class QRCodeStatusResponse(BaseModel):
    status: str
    cookies_saved: bool = False


# ── Accounts ──────────────────────────────────────────────────────────────────


class AccountInfo(BaseModel):
    uid: int
    nickname: str
    game: str
    server_name: str
    level: int


class FinishAccountsResponse(BaseModel):
    accounts: list[AccountInfo]
    status: str = "ok"


class AccountSubmitRequest(BaseModel):
    selected_accounts: list[str]  # list of "game_uid" strings e.g. "genshin_12345678"


# ── Gacha ─────────────────────────────────────────────────────────────────────


class GachaItem(BaseModel):
    id: int
    item_id: int
    rarity: int
    num: int
    num_since_last: int
    wish_id: str
    time: str
    banner_type: int
    name: str
    icon: str


class GachaLogResponse(BaseModel):
    items: list[GachaItem]
    total: int
    next_cursor: str | None
    game: str


class BannerTypeInfo(BaseModel):
    id: int
    name: str


class BannerTypesResponse(BaseModel):
    banner_types: list[BannerTypeInfo]


class GachaStatsResponse(BaseModel):
    total_pulls: int
    five_star_pity: int
    four_star_pity: int
    total_five_stars: int
    total_four_stars: int
    avg_pulls_per_five_star: float
    avg_pulls_per_four_star: float
    fifty_fifty_wins: int
    fifty_fifty_total: int
    fifty_fifty_win_rate: float


# ── i18n ──────────────────────────────────────────────────────────────────────


class I18nResponse(BaseModel):
    locale: str
    translations: dict[str, str]


# ── Geetest ───────────────────────────────────────────────────────────────────


class GeetestCommandRequest(BaseModel):
    account_id: int
    gt_type: str
    mmt_result: dict


# ── Errors ────────────────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    detail: str


class Params(BaseModel):
    locale: str = "en-US"
    user_id: int
    platform: Platform | None = None
    channel_id: int | None = None
    guild_id: int | None = None

    def to_query_string(self) -> str:
        return "&".join(
            f"{k}={v}" for k, v in self.model_dump().items() if v is not None and k != "user_id"
        )


class GachaParams(BaseModel):
    locale: str
    account_id: int
    banner_type: int
    rarities: list[int] = Field(default_factory=list)
    size: int = Field(default=100, ge=1, le=500)
    cursor: str | None = None
    name_contains: str | None = None

    @field_validator("rarities", mode="before")
    @classmethod
    def __parse_rarities(cls, value: str | list[int]) -> list[int]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [int(rarity) for rarity in value.split(",")]

    @field_validator("rarities", mode="after")
    @classmethod
    def __validate_rarities(cls, rarities: list[int]) -> list[int]:
        if not rarities:
            msg = "At least one rarity must be selected"
            raise ValueError(msg)

        if any(rarity not in {2, 3, 4, 5} for rarity in rarities):
            msg = "Invalid rarity"
            raise ValueError(msg)

        return rarities

    @field_validator("banner_type", mode="after")
    @classmethod
    def __validate_banner_type(cls, banner_type: int) -> int:
        banner_types = {key for game_dict in BANNER_TYPE_NAMES.values() for key in game_dict}
        if banner_type not in banner_types:
            msg = f"Invalid banner type {banner_type}"
            raise ValueError(msg)
        return banner_type

    def to_query_string(self) -> str:
        dict_model = self.model_dump()
        for key, value in dict_model.items():
            if isinstance(value, list):
                dict_model[key] = "" if not value else ",".join(str(v) for v in value)

        return "&".join(f"{k}={v}" for k, v in dict_model.items() if v is not None)
