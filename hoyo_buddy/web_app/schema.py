from __future__ import annotations

import urllib.parse
from typing import Self

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

    @classmethod
    def from_query_string(cls, query_string: str) -> Self:
        parsed = urllib.parse.parse_qs(query_string)
        parsed_dict = {k: v[0] for k, v in parsed.items()}
        return cls(**parsed_dict)  # pyright: ignore[reportArgumentType]
