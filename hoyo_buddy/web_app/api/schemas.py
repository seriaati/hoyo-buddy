from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# Re-export existing schemas from schema.py (they are Flet-free)
from hoyo_buddy.web_app.schema import GachaParams, Params

__all__ = [
    "AccountInfo",
    "AccountSubmitRequest",
    "AuthCallbackRequest",
    "AuthURLResponse",
    "DevToolsCookiesRequest",
    "DeviceInfoRequest",
    "EmailPasswordRequest",
    "EmailVerifyRequest",
    "ErrorResponse",
    "FinishAccountsResponse",
    "GachaIconsResponse",
    "GachaItem",
    "GachaLogResponse",
    "GachaNamesResponse",
    "GachaParams",
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
    next_step: Literal["geetest", "email_verify", "verify_otp", "finish", "redirect"]
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


class GachaLogResponse(BaseModel):
    items: list[GachaItem]
    total: int
    page: int
    max_page: int


class GachaIconsResponse(BaseModel):
    icons: dict[str, str]


class GachaNamesResponse(BaseModel):
    names: dict[str, str]


# ── i18n ──────────────────────────────────────────────────────────────────────


class I18nResponse(BaseModel):
    locale: str
    translations: dict[str, str]


# ── Errors ────────────────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    detail: str
