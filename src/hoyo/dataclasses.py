from typing import TYPE_CHECKING

from attr import dataclass

if TYPE_CHECKING:
    from aiohttp import web


@dataclass(kw_only=True)
class Reward:
    name: str
    amount: int
    index: int
    claimed: bool
    icon: str


@dataclass(kw_only=True)
class LoginNotifPayload:
    user_id: int
    guild_id: int | None = None
    channel_id: int
    message_id: int
    locale: str

    @classmethod
    def parse_from_request(cls, request: "web.Request") -> "LoginNotifPayload":
        return cls(
            user_id=int(request.query["user_id"]),
            guild_id=int(request.query["guild_id"]) if "guild_id" in request.query else None,
            channel_id=int(request.query["channel_id"]),
            message_id=int(request.query["message_id"]),
            locale=request.query["locale"],
        )

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "user_id": self.user_id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "locale": self.locale,
        }

    def to_query_string(self) -> str:
        return "&".join(f"{k}={v}" for k, v in self.to_dict().items() if v is not None)


@dataclass
class ItemWithDescription:
    icon: str
    title: str
    description: str


@dataclass
class ItemWithTrailing:
    icon: str
    title: str
    trailing: str
