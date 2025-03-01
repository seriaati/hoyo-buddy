from __future__ import annotations

from typing import Any, overload

import discord
import enka

from hoyo_buddy.db import EnkaCache

type ShowcaseResponse = enka.gi.ShowcaseResponse | enka.hsr.ShowcaseResponse


class BaseClient:
    def __init__(self, locale: discord.Locale = discord.Locale.american_english) -> None:
        self._locale = locale

    def _update_live_status(
        self,
        client: enka.HSRClient | enka.GenshinClient,
        data: dict[str, Any],
        extras: dict[str, dict[str, Any]],
        *,
        showcase: ShowcaseResponse | None = None,
        live: bool,
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
        showcase = showcase or client.parse_showcase(data)

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

    def _update_cache(
        self, game: enka.Game, *, cache: dict[str, Any], data: dict[str, Any]
    ) -> dict[str, Any]:
        if not cache:
            return data

        if game is enka.Game.GI:
            # Update player
            cache["playerInfo"] = data["playerInfo"]

            # Update characters
            if "avatarInfoList" not in data:
                # Showcase is disabled
                return cache

            if "avatarInfoList" not in cache:
                cache["avatarInfoList"] = []
            for chara in data["avatarInfoList"]:
                self.remove_character_from_cache(cache, str(chara["avatarId"]), game)
                cache["avatarInfoList"].append(chara)

            return cache
        if game is enka.Game.HSR:
            # Update player
            keys_to_update = (
                "nickname",
                "signature",
                "headIcon",
                "level",
                "worldLevel",
                "friendCount",
                "recordInfo",
            )
            for key in keys_to_update:
                if key not in data["detailInfo"]:
                    continue
                cache["detailInfo"][key] = data["detailInfo"][key]

            # Update characters
            if "avatarDetailList" not in data["detailInfo"]:
                # Showcase is disabled
                return cache

            if "avatarDetailList" not in cache["detailInfo"]:
                cache["detailInfo"]["avatarDetailList"] = []
            for chara in data["detailInfo"]["avatarDetailList"]:
                self.remove_character_from_cache(cache, str(chara["avatarId"]), game)
                cache["detailInfo"]["avatarDetailList"].append(chara)

            return cache

        msg = f"Game {game} is not supported."
        raise NotImplementedError(msg)

    @overload
    async def fetch_showcase(
        self, client: enka.HSRClient, uid: int
    ) -> tuple[enka.hsr.ShowcaseResponse, bool]: ...
    @overload
    async def fetch_showcase(
        self, client: enka.GenshinClient, uid: int
    ) -> tuple[enka.gi.ShowcaseResponse, bool]: ...
    async def fetch_showcase(
        self, client: enka.HSRClient | enka.GenshinClient, uid: int
    ) -> tuple[enka.hsr.ShowcaseResponse | enka.gi.ShowcaseResponse, bool]:
        """Fetch the showcase data for the given UID.

        Args:
            client: The client to use.
            uid: The UID to fetch the showcase data for.

        Returns:
            The showcase data.
        """
        cache, _ = await EnkaCache.get_or_create(uid=uid)
        showcase_cache = cache.hsr if client.game is enka.Game.HSR else cache.genshin
        errored = False

        try:
            live_data = await client.fetch_showcase(uid, raw=True)
        except enka.errors.EnkaAPIError:
            if not showcase_cache:
                raise

            errored = True
            self._update_live_status(client, showcase_cache, cache.extras, live=False)
            await cache.save(update_fields=("extras",))
        else:
            showcase_cache = self._update_cache(client.game, cache=showcase_cache, data=live_data)

            cache_showcase: ShowcaseResponse | None = None
            live_showcase: ShowcaseResponse | None = None
            try:
                cache_showcase = client.parse_showcase(showcase_cache)
                live_showcase = client.parse_showcase(live_data)
            except KeyError:
                await client.update_assets()

            self._update_live_status(
                client, showcase_cache, cache.extras, showcase=cache_showcase, live=False
            )
            self._update_live_status(
                client, live_data, cache.extras, showcase=live_showcase, live=True
            )

            if client.game is enka.Game.HSR:
                cache.hsr = showcase_cache
            elif client.game is enka.Game.GI:
                cache.genshin = showcase_cache
            else:
                msg = f"Game {client.game} is not supported."
                raise NotImplementedError(msg)

            update_fields = (
                ("hsr", "extras") if client.game is enka.Game.HSR else ("genshin", "extras")
            )
            await cache.save(update_fields=update_fields)

        return client.parse_showcase(showcase_cache), errored
