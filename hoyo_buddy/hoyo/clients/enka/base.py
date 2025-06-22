from __future__ import annotations

from typing import Any

import enka

from hoyo_buddy.enums import Locale

type ShowcaseResponse = enka.gi.ShowcaseResponse | enka.hsr.ShowcaseResponse


class BaseClient:
    def __init__(self, locale: Locale = Locale.american_english) -> None:
        self._locale = locale

    def _update_live_status(
        self, showcase: ShowcaseResponse, extras: dict[str, dict[str, Any]], *, live: bool
    ) -> dict[str, dict[str, Any]]:
        """Update the live status of the characters in the showcase data.

        Args:
            client: The client to use.
            data: The showcase data.
            extras: The extras data.
            live: The live status to update the characters to.

        Returns:
            The updated extras data.
        """
        cache_data = {"live": live, "locale": self._locale.value}
        for character in showcase.characters:
            if str(character.id) not in extras:
                extras[str(character.id)] = cache_data
            else:
                extras[str(character.id)].update(cache_data)

        return extras

    @staticmethod
    def remove_character_from_cache(
        cache: dict[str, Any], character_id: str, game: enka.Game
    ) -> None:
        """Remove the character from the cache.

        Args:
            cache: The cache to remove the character from.
            character_id: The ID of the character to remove.
            game: The game of the character to remove.
        """
        if game is enka.Game.GI:
            if "avatarInfoList" not in cache:
                return
            for character in cache["avatarInfoList"]:
                if str(character["avatarId"]) == character_id:
                    cache["avatarInfoList"].remove(character)
                    break
        elif game is enka.Game.HSR:
            if "avatarDetailList" not in cache["detailInfo"]:
                return
            for character in cache["detailInfo"]["avatarDetailList"]:
                if str(character["avatarId"]) == character_id:
                    cache["detailInfo"]["avatarDetailList"].remove(character)
                    break
