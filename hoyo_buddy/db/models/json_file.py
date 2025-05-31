# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import orjson
from tortoise import fields

from .base import BaseModel

if TYPE_CHECKING:
    import aiohttp


class JSONFile(BaseModel):
    name = fields.CharField(max_length=100, index=True)
    data: fields.Field[Any] = fields.JSONField()

    @staticmethod
    async def read(filename: str, *, default: Any = None, int_key: bool = False) -> Any:
        """Read a JSON file."""
        json_file = await JSONFile.get_or_none(name=filename)
        if json_file is None:
            if default is not None:
                return default
            return {}

        if int_key:
            return {int(key): value for key, value in json_file.data.items()}
        return json_file.data

    @staticmethod
    async def write(filename: str, data: Any, *, auto_str_key: bool = True) -> None:
        """Write a JSON file."""
        if auto_str_key:
            data = {str(key): value for key, value in data.items()}

        json_file = await JSONFile.get_or_none(name=filename)
        if json_file is None:
            await JSONFile.create(name=filename, data=data)
            return

        json_file.data = data
        await json_file.save(update_fields=("data",))

    @staticmethod
    async def fetch_and_cache(session: aiohttp.ClientSession, *, url: str, filename: str) -> Any:
        async with session.get(url) as resp:
            data = orjson.loads(await resp.text())
            await JSONFile.write(filename, data)
            return data
