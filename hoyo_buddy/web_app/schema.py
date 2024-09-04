from __future__ import annotations

from pydantic import BaseModel

from ..enums import Platform


class Params(BaseModel):
    locale: str
    user_id: int
    platform: Platform | None = None
    channel_id: int
    guild_id: int | None = None

    def to_query_string(self) -> str:
        return "&".join(f"{k}={v}" for k, v in self.model_dump().items() if v is not None)
