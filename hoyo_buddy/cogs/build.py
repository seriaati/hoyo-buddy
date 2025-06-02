from __future__ import annotations

from typing import TYPE_CHECKING

from discord import Locale, app_commands
from discord.ext import commands

from hoyo_buddy.commands.build import BuildCommand
from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.db import get_locale
from hoyo_buddy.db.utils import show_anniversary_dismissible
from hoyo_buddy.enums import Game
from hoyo_buddy.hoyo.clients import ambr, hakushin, yatta
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.types import Interaction


class Build(commands.GroupCog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    def _get_choices(self, locale: Locale, game: Game) -> list[app_commands.Choice[str]]:
        if game is Game.GENSHIN:
            characters = self.bot.autocomplete_choices[Game.GENSHIN][ambr.ItemCategory.CHARACTERS]
        elif game is Game.STARRAIL:
            characters = self.bot.autocomplete_choices[Game.STARRAIL][yatta.ItemCategory.CHARACTERS]
        elif game is Game.ZZZ:
            characters = self.bot.autocomplete_choices[Game.ZZZ][hakushin.ZZZItemCategory.AGENTS]
        else:
            characters = {}

        if not characters:
            return self.bot.get_error_choice(LocaleStr(key="search_autocomplete_not_setup"), locale)

        return characters.get(locale, characters[Locale.american_english])

    @app_commands.command(
        name=app_commands.locale_str("genshin"), description=COMMANDS["build genshin"].description
    )
    @app_commands.rename(
        character_id=app_commands.locale_str("character", key="akasha_character_param")
    )
    @app_commands.describe(
        character_id=app_commands.locale_str(
            "Character to view the build for", key="build_cmd_character_param_desc"
        )
    )
    async def genshin_build_command(self, i: Interaction, character_id: str) -> None:
        command = BuildCommand(Game.GENSHIN, character_id)
        await command.run(i)

        await show_anniversary_dismissible(i)

    @genshin_build_command.autocomplete("character_id")
    async def genshin_character_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)
        return [
            c for c in self._get_choices(locale, Game.GENSHIN) if current.lower() in c.name.lower()
        ][:25]


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Build(bot))
