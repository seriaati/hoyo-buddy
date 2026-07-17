from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

import genshin
from discord import app_commands
from discord.ext import commands, tasks
from loguru import logger

from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.constants import (
    HB_GAME_TO_GPY_GAME,
    get_describe_kwargs,
    get_rename_kwargs,
    locale_to_hoyo_lang,
)
from hoyo_buddy.db import get_locale
from hoyo_buddy.db.models import HoyoAccount, JSONFile
from hoyo_buddy.exceptions import AutocompleteNotDoneYetError, InvalidQueryError
from hoyo_buddy.hoyo.clients.gpy import ProxyGenshinClient
from hoyo_buddy.hoyo.transformers import HoyoAccountTransformer
from hoyo_buddy.types import Interaction
from hoyo_buddy.ui.hoyo.accompany import AccompanyView
from hoyo_buddy.utils import ephemeral
from hoyo_buddy.utils.misc import handle_autocomplete_errors

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy

CHARACTERS_FILENAME = "accompany_characters_{lang}.json"
CHARACTER_LIST_ENDPOINT = "community/painter/api/getChannelRoleList"


class Accompany(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot
        self._characters: dict[str, list[genshin.models.AccompanyCharacterGame]] = {}
        self._fetch_tasks: dict[str, asyncio.Task[None]] = {}

    async def cog_load(self) -> None:
        try:
            await self._load_characters("en-us")
        except Exception as e:
            logger.warning(f"Failed to load accompany characters on cog load: {e}")
        self._refresh_characters.start()

    async def cog_unload(self) -> None:
        self._refresh_characters.cancel()

    @staticmethod
    def _parse_characters(data: Any) -> list[genshin.models.AccompanyCharacterGame]:
        return [genshin.models.AccompanyCharacterGame(**i) for i in data["game_roles_list"]]

    @staticmethod
    def _game_matches(
        game: genshin.models.AccompanyCharacterGame, target: genshin.Game | None
    ) -> bool:
        try:
            game_ = game.game
        except ValueError:
            # The game ID isn't mapped to a known game in genshin.py
            return False
        return target is None or game_ == target

    async def _fetch_characters(self, lang: str) -> list[genshin.models.AccompanyCharacterGame]:
        client = ProxyGenshinClient()
        data = await client.request_bbs(CHARACTER_LIST_ENDPOINT, method="POST", lang=lang)
        characters = self._parse_characters(data)
        self._characters[lang] = characters
        await JSONFile.write(CHARACTERS_FILENAME.format(lang=lang), data)
        return characters

    async def _load_characters(self, lang: str) -> list[genshin.models.AccompanyCharacterGame]:
        """Get characters from memory, else fetch fresh, else fall back to the DB cache."""
        if (cached := self._characters.get(lang)) is not None:
            return cached

        try:
            return await self._fetch_characters(lang)
        except Exception:
            data = await JSONFile.read(CHARACTERS_FILENAME.format(lang=lang), default=None)
            if data is None:
                raise
            characters = self._parse_characters(data)
            self._characters[lang] = characters
            return characters

    async def _lazy_load_characters(self, lang: str) -> None:
        try:
            await self._load_characters(lang)
        except Exception as e:
            logger.warning(f"Failed to fetch accompany characters for lang {lang!r}: {e}")
        finally:
            self._fetch_tasks.pop(lang, None)

    def _get_cached_characters(
        self, lang: str
    ) -> list[genshin.models.AccompanyCharacterGame] | None:
        cached = self._characters.get(lang)
        if cached is None and lang not in self._fetch_tasks:
            self._fetch_tasks[lang] = asyncio.create_task(self._lazy_load_characters(lang))
        return cached or self._characters.get("en-us")

    @tasks.loop(hours=6)
    async def _refresh_characters(self) -> None:
        if self._refresh_characters.current_loop == 0:
            # Characters were just fetched in cog_load
            return

        for lang in tuple(self._characters):
            try:
                await self._fetch_characters(lang)
            except Exception as e:
                logger.warning(f"Failed to refresh accompany characters for lang {lang!r}: {e}")

    @app_commands.command(
        name=app_commands.locale_str("accompany"), description=COMMANDS["accompany"].description
    )
    @app_commands.rename(
        character=app_commands.locale_str("character", key="accompany_cmd_character_param_name"),
        **get_rename_kwargs(account=True),
    )
    @app_commands.describe(
        character=app_commands.locale_str(
            "Character to view, defaults to the first available one",
            key="accompany_cmd_character_param_desc",
        ),
        **get_describe_kwargs(account=True),
    )
    async def accompany_command(
        self,
        i: Interaction,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["accompany"].games)
        ] = None,
        character: str | None = None,
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        config = COMMANDS["accompany"]
        account = account or await self.bot.get_account(i.user.id, config.games, config.platform)
        locale = await get_locale(i)

        games = await self._load_characters(locale_to_hoyo_lang(locale))
        characters = next(
            (
                game.characters
                for game in games
                if self._game_matches(game, HB_GAME_TO_GPY_GAME[account.game])
            ),
            None,
        )
        if not characters:
            raise InvalidQueryError

        chosen = characters[0]
        if character is not None:
            try:
                role_id = int(character.split(":", maxsplit=1)[0])
            except ValueError as e:
                raise InvalidQueryError from e

            chosen_ = next((c for c in characters if c.info.role_id == role_id), None)
            if chosen_ is None:
                raise InvalidQueryError
            chosen = chosen_

        view = AccompanyView(
            account=account, characters=characters, character=chosen, author=i.user, locale=locale
        )
        await view.start(i)

    @accompany_command.autocomplete("account")
    @handle_autocomplete_errors
    async def account_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current)

    @accompany_command.autocomplete("character")
    @handle_autocomplete_errors
    async def character_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)
        games = self._get_cached_characters(locale_to_hoyo_lang(locale))
        if games is None:
            raise AutocompleteNotDoneYetError

        target_game: genshin.Game | None = None
        account_value: str | None = i.namespace.account
        if account_value:
            with contextlib.suppress(ValueError):
                account = await HoyoAccount.get_or_none(id=int(account_value))
                if account is not None:
                    target_game = HB_GAME_TO_GPY_GAME[account.game]

        current = current.lower()
        choices: list[app_commands.Choice[str]] = []
        for game in games:
            if not self._game_matches(game, target_game):
                continue
            for char in game.characters:
                choice_name = f"{char.info.name} ({char.info.game_name})"
                if current and current not in choice_name.lower():
                    continue
                choices.append(
                    app_commands.Choice(
                        name=choice_name, value=f"{char.info.role_id}:{char.info.topic_id}"
                    )
                )
        return choices[:25]


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Accompany(bot))
