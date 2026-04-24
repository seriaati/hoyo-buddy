from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from hoyo_buddy.enums import GeetestType

if TYPE_CHECKING:
    from collections.abc import Mapping


__all__ = ("GeetestCommandPayload", "GeetestLoginPayload")


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

    mmt_gt: str
    mmt_challenge: str
    mmt_new_captcha: int
    mmt_success: int
    mmt_session_id: str | None = None
    mmt_check_id: str | None = None
    mmt_risk_type: str | None = None

    def to_query_string(self) -> str:
        return "&".join(
            f"{k}={v}" for k, v in self.model_dump(mode="json").items() if v is not None
        )


class GeetestLoginPayload(BaseModel):
    user_id: int
    gt_version: int
    api_server: str = "api-na.geetest.com"
    locale: str

    @classmethod
    def parse_from_request(cls, query: Mapping[str, str]) -> GeetestLoginPayload:
        return cls(
            user_id=int(query["user_id"]),
            gt_version=int(query["gt_version"]),
            api_server=query["api_server"],
            locale=query["locale"],
        )

    def to_query_string(self) -> str:
        return "&".join(f"{k}={v}" for k, v in self.model_dump(mode="json").items())
