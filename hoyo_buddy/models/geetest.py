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
