from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from ..bot import INTERACTION, HoyoBuddy, LocaleStr, Translator
from ..bot.emojis import PROJECT_AMBER
from ..db import Game, HoyoAccount, Settings
from ..exceptions import InvalidQueryError, NoAccountFoundError
from ..hoyo.genshin import ambr
from ..hoyo.transformers import HoyoAccountTransformer  # noqa: TCH001
from ..ui.hoyo.checkin import CheckInUI
from ..ui.hoyo.search.artifact_set import ArtifactSetUI
from ..ui.hoyo.search.character import CharacterUI
from ..ui.hoyo.search.weapon import WeaponUI
from ..ui.ui import URLButtonView


class Hoyo(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    @staticmethod
    async def _account_autocomplete(
        user_id: int,
        current: str,
        locale: discord.Locale,
        translator: Translator,
    ) -> list[discord.app_commands.Choice]:
        accounts = await HoyoAccount.filter(user_id=user_id).all()
        if not accounts:
            return [
                discord.app_commands.Choice(
                    name=discord.app_commands.locale_str(
                        "You don't have any accounts yet. Add one with /accounts",
                        key="no_accounts_autocomplete_choice",
                    ),
                    value="none",
                )
            ]

        return [
            discord.app_commands.Choice(
                name=f"{account} | {translator.translate(LocaleStr(account.game, warn_no_key=False), locale)}",
                value=f"{account.uid}_{account.game}",
            )
            for account in accounts
            if current.lower() in str(account).lower()
        ]

    @staticmethod
    def _get_error_app_command_choice(error_message: str) -> app_commands.Choice[str]:
        return app_commands.Choice(
            name=app_commands.locale_str(error_message, warn_no_key=False),
            value="none",
        )

    @app_commands.command(
        name=app_commands.locale_str("check-in", translate=False),
        description=app_commands.locale_str(
            "Game daily check-in", key="checkin_command_description"
        ),
    )
    @app_commands.rename(
        account=app_commands.locale_str("account", key="account_autocomplete_param_name")
    )
    @app_commands.describe(
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the first one",
            key="account_autocomplete_param_description",
        )
    )
    async def checkin_command(
        self,
        i: INTERACTION,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> Any:
        settings = await Settings.get(user_id=i.user.id)
        if account is None:
            account = await HoyoAccount.filter(user_id=i.user.id).first()
            if account is None:
                raise NoAccountFoundError

        view = CheckInUI(
            account,
            dark_mode=settings.dark_mode,
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @checkin_command.autocomplete("account")
    async def check_in_command_autocomplete(
        self, i: INTERACTION, current: str
    ) -> list[app_commands.Choice]:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        return await self._account_autocomplete(i.user.id, current, locale, self.bot.translator)

    @app_commands.command(
        name=app_commands.locale_str("search", translate=False),
        description=app_commands.locale_str(
            "Search anything game related", key="search_command_description"
        ),
    )
    @app_commands.rename(
        game_value=app_commands.locale_str("game", key="search_command_game_param_name"),
        category_value=app_commands.locale_str(
            "category", key="search_command_category_param_name"
        ),
        query=app_commands.locale_str("query", key="search_command_query_param_name"),
    )
    @app_commands.describe(
        game_value=app_commands.locale_str(
            "Game to search in", key="search_command_game_param_description"
        ),
        category_value=app_commands.locale_str(
            "Category to search in", key="search_command_category_param_description"
        ),
        query=app_commands.locale_str(
            "Query to search for", key="search_command_query_param_description"
        ),
    )
    @app_commands.choices(
        game_value=[
            app_commands.Choice(
                name=app_commands.locale_str(Game.GENSHIN.value, warn_no_key=False),
                value=Game.GENSHIN.value,
            ),
            app_commands.Choice(
                name=app_commands.locale_str(Game.STARRAIL.value, warn_no_key=False),
                value=Game.STARRAIL.value,
            ),
        ]
    )
    async def search_command(  # noqa: PLR0911
        self,
        i: INTERACTION,
        game_value: str,
        category_value: str,
        query: str,
    ) -> Any:
        if category_value == "none" or query == "none":
            raise InvalidQueryError

        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        game = Game(game_value)

        if game is Game.GENSHIN:
            category = ambr.ItemCategory(category_value)

            if category is ambr.ItemCategory.CHARACTERS:
                character_ui = CharacterUI(
                    query,
                    author=i.user,
                    locale=locale,
                    translator=i.client.translator,
                )
                return await character_ui.update(i)

            if category is ambr.ItemCategory.WEAPONS:
                weapon_ui = WeaponUI(
                    query,
                    author=i.user,
                    locale=locale,
                    translator=i.client.translator,
                )
                return await weapon_ui.update(i)

            if category is ambr.ItemCategory.NAMECARDS:
                async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    namecard_detail = await api.fetch_namecard_detail(int(query))
                    embed = api.get_namecard_embed(namecard_detail)
                    return await i.followup.send(embed=embed)

            if category is ambr.ItemCategory.ARTIFACT_SETS:
                artifact_set_ui = ArtifactSetUI(
                    query,
                    author=i.user,
                    locale=locale,
                    translator=i.client.translator,
                )
                return await artifact_set_ui.update(i)

            if category is ambr.ItemCategory.FOOD:
                async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    food_detail = await api.fetch_food_detail(int(query))
                    embed = api.get_food_embed(food_detail)
                    return await i.followup.send(embed=embed)

            if category is ambr.ItemCategory.MATERIALS:
                async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    material_detail = await api.fetch_material_detail(int(query))
                    embed = api.get_material_embed(material_detail)
                    return await i.followup.send(embed=embed)

            if category is ambr.ItemCategory.FURNISHINGS:
                async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    furniture_detail = await api.fetch_furniture_detail(int(query))
                    embed = api.get_furniture_embed(furniture_detail)
                    return await i.followup.send(
                        embed=embed,
                        view=URLButtonView(
                            i.client.translator,
                            locale,
                            url=f"https://ambr.top/{api.lang.value}/archive/furniture/{query}/",
                            label="ambr.top",
                            emoji=PROJECT_AMBER,
                        ),
                    )

    @search_command.autocomplete("category_value")
    async def search_command_category_autocomplete(
        self, i: INTERACTION, current: str
    ) -> list[app_commands.Choice]:
        await i.response.defer()

        try:
            game = Game(i.namespace.game)
        except ValueError:
            return [self._get_error_app_command_choice("Invalid game selected")]

        if game is Game.GENSHIN:
            return [
                app_commands.Choice(
                    name=app_commands.locale_str(c.value, warn_no_key=False),
                    value=c.value,
                )
                for c in ambr.ItemCategory
                if current.lower() in c.value.lower()
            ]

        return [self._get_error_app_command_choice("Invalid game selected")]

    @search_command.autocomplete("query")
    async def search_command_query_autocomplete(  # noqa: C901
        self, i: INTERACTION, current: str
    ) -> list[app_commands.Choice]:
        await i.response.defer()

        try:
            game = Game(i.namespace.game)
        except ValueError:
            return [self._get_error_app_command_choice("Invalid game selected")]
        if game is Game.GENSHIN:
            try:
                category = ambr.ItemCategory(i.namespace.category)
            except ValueError:
                return [self._get_error_app_command_choice("Invalid category selected")]
        else:
            return [self._get_error_app_command_choice("Invalid game selected")]

        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
            if category is ambr.ItemCategory.CHARACTERS:
                items = await api.fetch_characters()
            elif category is ambr.ItemCategory.WEAPONS:
                items = await api.fetch_weapons()
            elif category is ambr.ItemCategory.NAMECARDS:
                items = await api.fetch_namecards()
            elif category is ambr.ItemCategory.ARTIFACT_SETS:
                items = await api.fetch_artifact_sets()
            elif category is ambr.ItemCategory.FOOD:
                items = await api.fetch_foods()
            elif category is ambr.ItemCategory.MATERIALS:
                items = await api.fetch_materials()
            elif category is ambr.ItemCategory.FURNISHINGS:
                items = await api.fetch_furnitures()
            else:
                return [self._get_error_app_command_choice("Invalid category selected")]
            return [
                app_commands.Choice(name=item.name, value=str(item.id))
                for item in items
                if current.lower() in item.name.lower()
            ][:25]


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Hoyo(bot))
