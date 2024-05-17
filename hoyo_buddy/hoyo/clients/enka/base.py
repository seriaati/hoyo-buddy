from __future__ import annotations

import logging
from typing import Any, overload

import discord
import enka

from ....db.models import EnkaCache

LOGGER_ = logging.getLogger(__name__)


class BaseClient:
    def __init__(self, locale: discord.Locale = discord.Locale.american_english) -> None:
        self._locale = locale

    @overload
    def _update_live_status(
        self,
        client: enka.HSRClient,
        data: dict[str, Any],
        extras: dict[str, dict[str, Any]],
        live: bool,
    ) -> enka.hsr.ShowcaseResponse: ...
    @overload
    def _update_live_status(
        self,
        client: enka.GenshinClient,
        data: dict[str, Any],
        extras: dict[str, dict[str, Any]],
        live: bool,
    ) -> enka.gi.ShowcaseResponse: ...
    def _update_live_status(
        self,
        client: enka.HSRClient | enka.GenshinClient,
        data: dict[str, Any],
        extras: dict[str, dict[str, Any]],
        live: bool,
    ) -> enka.hsr.ShowcaseResponse | enka.gi.ShowcaseResponse:
        """Update the live status of the characters in the showcase data.

        Args:
            client: The client to use.
            data: The showcase data.
            extras: The extras data.
            live: The live status to update the characters to.

        Returns:
            The showcase data with the updated live status.
        """
        showcase = client.parse_showcase(data)
        for character in showcase.characters:
            if str(character.id) not in extras:
                extras[str(character.id)] = {"live": live, "locale": self._locale.value}
            else:
                extras[str(character.id)].update({"live": live})

        return showcase

    @overload
    async def fetch_showcase(
        self, client: enka.HSRClient, uid: int
    ) -> enka.hsr.ShowcaseResponse: ...
    @overload
    async def fetch_showcase(
        self, client: enka.GenshinClient, uid: int
    ) -> enka.gi.ShowcaseResponse: ...
    async def fetch_showcase(
        self, client: enka.HSRClient | enka.GenshinClient, uid: int
    ) -> enka.hsr.ShowcaseResponse | enka.gi.ShowcaseResponse:
        """Fetch the showcase data for the given UID.

        Args:
            client: The client to use.
            uid: The UID to fetch the showcase data for.

        Returns:
            The showcase data.
        """
        cache, _ = await EnkaCache.get_or_create(uid=uid)
        showcase_cache = cache.hsr if isinstance(client, enka.HSRClient) else cache.genshin

        try:
            live_data = await client.fetch_showcase(uid, raw=True)
        except enka.errors.GameMaintenanceError:
            if not showcase_cache:
                raise

            self._update_live_status(client, showcase_cache, cache.extras, False)
            await cache.save(update_fields=("extras",))
        else:
            showcase_cache.update(live_data)

            self._update_live_status(client, showcase_cache, cache.extras, False)
            self._update_live_status(client, live_data, cache.extras, True)

            update_fields = (
                ("hsr", "extras") if isinstance(client, enka.HSRClient) else ("genshin", "extras")
            )
            await cache.save(update_fields=update_fields)

        return client.parse_showcase(showcase_cache)
