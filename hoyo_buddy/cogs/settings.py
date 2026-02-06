from __future__ import annotations

from typing import TYPE_CHECKING, Any

from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.constants import ZZZ_AVATAR_BATTLE_TEMP_JSON
from hoyo_buddy.db import Settings as UserSettings
from hoyo_buddy.db.models.json_file import JSONFile
from hoyo_buddy.db.utils import get_card_settings, get_locale, set_highlight_substats
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.exceptions import InvalidQueryError
from hoyo_buddy.hoyo.clients import ambr, hakushin, yatta
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.settings.view import CardSettingsView, SettingsView
from hoyo_buddy.utils.misc import handle_autocomplete_errors

from ..types import Interaction

if TYPE_CHECKING:
    from ..bot import HoyoBuddy


class Settings(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    def _get_choices(self, locale: Locale, game: Game) -> list[app_commands.Choice[str]]:
        """Get character autocomplete choices."""
        if game is Game.GENSHIN:
            category = ambr.ItemCategory.CHARACTERS
        elif game is Game.STARRAIL:
            category = yatta.ItemCategory.CHARACTERS
        elif game is Game.ZZZ:
            category = hakushin.ZZZItemCategory.AGENTS
        else:
            return self.bot.get_error_choice(LocaleStr(key="invalid_game_selected"), locale)

        characters = self.bot.search_autofill[game][category]
        if not characters:
            return self.bot.get_error_choice(LocaleStr(key="search_autocomplete_not_setup"), locale)

        return characters.get(locale, characters[Locale.american_english])

    def _get_character_name(self, game: Game, character_id: str, locale: Locale) -> str | None:
        choices = self._get_choices(locale, game)
        for choice in choices:
            if choice.value == character_id:
                return choice.name
        return None

    @app_commands.command(name=locale_str("settings"), description=COMMANDS["settings"].description)
    async def settings_command(self, i: Interaction) -> Any:
        await i.response.defer(ephemeral=True)

        view = SettingsView(author=i.user, locale=await get_locale(i))
        await view.update(i)

    async def _card_settings_command(self, i: Interaction, game: Game, character_id: str) -> Any:
        await i.response.defer(ephemeral=True)

        locale = await get_locale(i)

        character_name = self._get_character_name(game, character_id, locale)
        if character_name is None:
            raise InvalidQueryError

        card_settings = await get_card_settings(i.user.id, character_id, game=game)
        settings = await UserSettings.get(user_id=i.user.id)

        if not card_settings.highlight_substats:
            agent_special_stat_map: dict[str, list[int]] = await JSONFile.read(
                ZZZ_AVATAR_BATTLE_TEMP_JSON
            )
            await set_highlight_substats(
                agent_special_stat_map=agent_special_stat_map,
                card_settings=card_settings,
                character_id=int(character_id),
            )

        view = CardSettingsView(
            card_settings=card_settings,
            settings=settings,
            character_name=character_name,
            game=game,
            author=i.user,
            locale=locale,
        )
        await view.update(i)

    card_settings = app_commands.Group(
        name=locale_str("card-settings"), description="Card settings commands"
    )

    @card_settings.command(
        name=locale_str("genshin"), description=COMMANDS["card_settings genshin"].description
    )
    @app_commands.rename(
        character_id=app_commands.locale_str("character", key="akasha_character_param")
    )
    @app_commands.describe(
        character_id=locale_str(
            "Character to modify the card settings for", key="card_settings_character_param"
        )
    )
    async def gi_card_settings_command(self, i: Interaction, character_id: str) -> Any:
        await self._card_settings_command(i, Game.GENSHIN, character_id)

    @card_settings.command(
        name=locale_str("hsr"), description=COMMANDS["card_settings hsr"].description
    )
    @app_commands.rename(
        character_id=app_commands.locale_str("character", key="akasha_character_param")
    )
    @app_commands.describe(
        character_id=locale_str(
            "Character to modify the card settings for", key="card_settings_character_param"
        )
    )
    async def hsr_card_settings_command(self, i: Interaction, character_id: str) -> Any:
        await self._card_settings_command(i, Game.STARRAIL, character_id)

    @card_settings.command(
        name=locale_str("zzz"), description=COMMANDS["card_settings zzz"].description
    )
    @app_commands.rename(
        character_id=app_commands.locale_str("character", key="akasha_character_param")
    )
    @app_commands.describe(
        character_id=locale_str(
            "Character to modify the card settings for", key="card_settings_character_param"
        )
    )
    async def zzz_card_settings_command(self, i: Interaction, character_id: str) -> Any:
        await self._card_settings_command(i, Game.ZZZ, character_id)

    @gi_card_settings_command.autocomplete("character_id")
    @handle_autocomplete_errors
    async def gi_query_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice]:
        locale = await get_locale(i)
        choices = [
            c for c in self._get_choices(locale, Game.GENSHIN) if current.lower() in c.name.lower()
        ]
        return choices[:25]

    @hsr_card_settings_command.autocomplete("character_id")
    @handle_autocomplete_errors
    async def hsr_query_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice]:
        locale = await get_locale(i)
        choices = [
            c for c in self._get_choices(locale, Game.STARRAIL) if current.lower() in c.name.lower()
        ]
        return choices[:25]

    @zzz_card_settings_command.autocomplete("character_id")
    @handle_autocomplete_errors
    async def zzz_query_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice]:
        locale = await get_locale(i)
        choices = [
            c for c in self._get_choices(locale, Game.ZZZ) if current.lower() in c.name.lower()
        ]
        return choices[:25]


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Settings(bot))
