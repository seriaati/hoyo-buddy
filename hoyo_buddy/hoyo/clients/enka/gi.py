from __future__ import annotations

import logging

import enka

from ....constants import LOCALE_TO_GI_ENKA_LANG
from .base import BaseClient

LOGGER_ = logging.getLogger(__name__)


class EnkaGIClient(BaseClient):
    async def get_character_talent_order(self, character_id: str) -> list[int]:
        async with enka.GenshinClient(
            lang=LOCALE_TO_GI_ENKA_LANG.get(self._locale, enka.gi.Language.ENGLISH)
        ) as client:
            if character_id not in client._assets.character_data:
                msg = f"Character ID {character_id} not found in Enka character data"
                raise ValueError(msg)

            return client._assets.character_data[character_id]["SkillOrder"]

    async def fetch_showcase(self, uid: int) -> enka.gi.ShowcaseResponse:
        async with enka.GenshinClient(
            lang=LOCALE_TO_GI_ENKA_LANG.get(self._locale, enka.gi.Language.ENGLISH)
        ) as client:
            return await super().fetch_showcase(client, uid)
