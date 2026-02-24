from __future__ import annotations

from typing import TYPE_CHECKING

import hb_data
import szgf
from discord import app_commands
from discord.ext import commands
from loguru import logger

from hoyo_buddy.commands.build import BuildCommand
from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.constants import locale_to_zenless_data_lang
from hoyo_buddy.db import get_locale
from hoyo_buddy.dismissibles import show_anniversary_dismissible
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.hoyo.clients import ambr, yatta
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.types import Interaction

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy


class Build(commands.GroupCog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot
        self.guides: dict[str, szgf.ParsedGuide] = {}

    async def cog_load(self) -> None:
        await self.reload_szgf_guides()
        logger.debug(f"Loaded {len(self.guides)} ZZZ guides")

    async def reload_szgf_guides(self) -> None:
        async with szgf.SZGFClient() as client:
            await client.download_guides()
            self.guides = await client.read_guides()

    def _get_choices(self, locale: Locale, game: Game) -> list[app_commands.Choice[str]]:
        if game is Game.GENSHIN:
            characters = self.bot.search_autofill[Game.GENSHIN][ambr.ItemCategory.CHARACTERS]
        elif game is Game.STARRAIL:
            characters = self.bot.search_autofill[Game.STARRAIL][yatta.ItemCategory.CHARACTERS]
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

    @app_commands.command(
        name=app_commands.locale_str("zzz"), description=COMMANDS["build zzz"].description
    )
    @app_commands.rename(
        character_id=app_commands.locale_str("character", key="akasha_character_param")
    )
    @app_commands.describe(
        character_id=app_commands.locale_str(
            "Character to view the build for", key="build_cmd_character_param_desc"
        )
    )
    async def zzz_build_command(self, i: Interaction, character_id: str) -> None:
        command = BuildCommand(Game.ZZZ, character_id)
        await command.run(i)

        await show_anniversary_dismissible(i)

    @zzz_build_command.autocomplete("character_id")
    async def zzz_character_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)

        async with hb_data.ZZZClient() as client:
            characters = client.get_characters(
                lang=hb_data.zzz.Language(locale_to_zenless_data_lang(locale))
            )

        return [
            app_commands.Choice(name=c.name, value=str(c.id))
            for c in characters
            if current.lower() in c.name.lower() and str(c.id) in self.guides
        ][:25]

    @commands.is_owner()
    @commands.command(name="rguides")
    async def reload_guides(self, ctx: commands.Context) -> None:
        await self.reload_szgf_guides()
        await ctx.send(f"Reloaded {len(self.guides)} ZZZ guides")


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Build(bot))
