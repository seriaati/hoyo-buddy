from __future__ import annotations

import enka

from hoyo_buddy.constants import LOCALE_TO_GI_ENKA_LANG

from .base import BaseClient


class EnkaGIClient(BaseClient):
    async def get_character_talent_order(self, character_id: str) -> list[int]:
        async with enka.GenshinClient(
            lang=LOCALE_TO_GI_ENKA_LANG.get(self._locale, enka.gi.Language.ENGLISH)
        ) as client:
            if character_id not in client._assets.character_data:
                msg = f"Character ID {character_id} not found in Enka character data"
                raise ValueError(msg)

            return client._assets.character_data[character_id]["SkillOrder"]

    async def fetch_showcase(self, uid: int) -> tuple[enka.gi.ShowcaseResponse, bool]:
        async with enka.GenshinClient(
            lang=LOCALE_TO_GI_ENKA_LANG.get(self._locale, enka.gi.Language.ENGLISH)
        ) as client:
            return await super().fetch_showcase(client, uid)

    async def fetch_builds(self, owner: enka.Owner) -> dict[str, list[enka.gi.Build]]:
        async with enka.GenshinClient(
            lang=LOCALE_TO_GI_ENKA_LANG.get(self._locale, enka.gi.Language.ENGLISH)
        ) as client:
            return await client.fetch_builds(owner)
