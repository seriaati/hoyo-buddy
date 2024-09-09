from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from ..enums import Platform


class Params(BaseModel):
    locale: str
    user_id: int
    platform: Platform | None = None
    channel_id: int
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
    size: int = 100
    page: int = 1
    name_contains: str | None = None

    @field_validator("rarities", mode="before")
    @classmethod
    def __parse_rarities(cls, value: str | list[int]) -> list[int]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [int(rarity) for rarity in value.split(",")]

    def to_query_string(self) -> str:
        dict_model = self.model_dump()
        for key, value in dict_model.items():
            if isinstance(value, list):
                dict_model[key] = "" if not value else ",".join(str(v) for v in value)

        return "&".join(f"{k}={v}" for k, v in dict_model.items() if v is not None)
