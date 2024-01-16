import logging
import random
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ..bot import INTERACTION, HoyoBuddy, LocaleStr, Translator
from ..bot.emojis import PROJECT_AMBER
from ..db import Game, HoyoAccount, Settings
from ..exceptions import InvalidQueryError, NoAccountFoundError
from ..hoyo.genshin import ambr
from ..hoyo.hsr import yatta
from ..hoyo.transformers import HoyoAccountTransformer  # noqa: TCH001
from ..ui import URLButtonView
from ..ui.hoyo.checkin import CheckInUI
from ..ui.hoyo.search.genshin import ArtifactSetUI, BookVolumeUI, CharacterUI, TCGCardUI, WeaponUI
from ..ui.hoyo.search.hsr import BookUI, RelicSetUI
from ..ui.hoyo.search.hsr.character import CharacterUI as HSRCharacterUI

LOGGER_ = logging.getLogger(__name__)


class Hoyo(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

        self._search_categories: dict[Game, list[str]] = {
            Game.GENSHIN: [c.value for c in ambr.ItemCategory],
            Game.STARRAIL: [c.value for c in yatta.ItemCategory],
        }

        # [game][category][locale][item_name] -> item_id
        self._search_autocomplete_choices: dict[
            Game,
            dict[
                ambr.ItemCategory | yatta.ItemCategory,
                dict[str, dict[str, str]],
            ],
        ] = {}

    async def cog_load(self) -> None:
        self._update_search_autocomplete_choices.start()

    async def cog_unload(self) -> None:
        self._update_search_autocomplete_choices.cancel()

    async def _setup_search_autocomplete_choices(self) -> None:
        LOGGER_.info("Setting up search autocomplete choices")
        start = self.bot.loop.time()

        for item_category in ambr.ItemCategory:
            for locale in ambr.LOCALE_TO_LANG:
                async with ambr.AmbrAPIClient(locale, self.bot.translator) as api:
                    items = await api.fetch_items(item_category)
                    category_locale_choices = (
                        self._search_autocomplete_choices.setdefault(Game.GENSHIN, {})
                        .setdefault(item_category, {})
                        .setdefault(locale.value, {})
                    )
                    for item in items:
                        category_locale_choices[item.name] = str(item.id)

        for item_category in yatta.ItemCategory:
            for locale in yatta.LOCALE_TO_LANG:
                async with yatta.YattaAPIClient(locale, self.bot.translator) as api:
                    items = await api.fetch_items_(item_category)
                    category_locale_choices = (
                        self._search_autocomplete_choices.setdefault(Game.STARRAIL, {})
                        .setdefault(item_category, {})
                        .setdefault(locale.value, {})
                    )
                    for item in items:
                        category_locale_choices[item.name] = str(item.id)

        LOGGER_.info(
            "Finished setting up search autocomplete choices, took %.2f seconds",
            self.bot.loop.time() - start,
        )

    @tasks.loop(hours=24)
    async def _update_search_autocomplete_choices(self) -> None:
        await self._setup_search_autocomplete_choices()

    @_update_search_autocomplete_choices.before_loop
    async def _before_update_search_autocomplete_choices(self) -> None:
        await self.bot.wait_until_ready()

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
    async def search_command(  # noqa: C901, PLR0911, PLR0912, PLR0914, PLR0915
        self,
        i: INTERACTION,
        game_value: str,
        category_value: str,
        query: str,
    ) -> Any:
        if category_value == "none" or query == "none":
            raise InvalidQueryError
        try:
            game = Game(game_value)
        except ValueError as e:
            raise InvalidQueryError from e

        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale

        if game is Game.GENSHIN:
            try:
                category = ambr.ItemCategory(category_value)
            except ValueError as e:
                raise InvalidQueryError from e

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
                return await weapon_ui.start(i)

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
                return await artifact_set_ui.start(i)

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

            if category is ambr.ItemCategory.FURNISHING_SETS:
                async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    furniture_set_detail = await api.fetch_furniture_set_detail(int(query))
                    embed = api.get_furniture_set_embed(furniture_set_detail)
                    return await i.followup.send(
                        embed=embed,
                        view=URLButtonView(
                            i.client.translator,
                            locale,
                            url=f"https://ambr.top/{api.lang.value}/archive/furnitureSuite/{query}/",
                            label="ambr.top",
                            emoji=PROJECT_AMBER,
                        ),
                    )

            if category is ambr.ItemCategory.LIVING_BEINGS:
                async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    monster_detail = await api.fetch_monster_detail(int(query))
                    embed = api.get_monster_embed(monster_detail)
                    return await i.followup.send(
                        embed=embed,
                        view=URLButtonView(
                            i.client.translator,
                            locale,
                            url=f"https://ambr.top/{api.lang.value}/archive/monster/{query}/",
                            label="ambr.top",
                            emoji=PROJECT_AMBER,
                        ),
                    )

            if category is ambr.ItemCategory.BOOKS:
                async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    book = await api.fetch_book_detail(int(query))
                    book_volume_ui = BookVolumeUI(
                        book,
                        api.lang.value,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    return await book_volume_ui.start(i)

            if category is ambr.ItemCategory.TCG:
                tcg_card_ui = TCGCardUI(
                    int(query), author=i.user, locale=locale, translator=i.client.translator
                )
                return await tcg_card_ui.start(i)
        elif game is Game.STARRAIL:
            try:
                category = yatta.ItemCategory(category_value)
            except ValueError as e:
                raise InvalidQueryError from e

            if category is yatta.ItemCategory.ITEMS:
                async with yatta.YattaAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    item = await api.fetch_item_detail(int(query))
                    embed = api.get_item_embed(item)
                    return await i.followup.send(embed=embed)

            if category is yatta.ItemCategory.LIGHT_CONES:
                async with yatta.YattaAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    light_cone = await api.fetch_light_cone_detail(int(query))
                    embed = api.get_light_cone_embed(light_cone)
                    return await i.followup.send(embed=embed)

            if category is yatta.ItemCategory.BOOKS:
                book_ui = BookUI(
                    query, author=i.user, locale=locale, translator=i.client.translator
                )
                return await book_ui.start(i)

            if category is yatta.ItemCategory.RELICS:
                relic_set_ui = RelicSetUI(
                    query, author=i.user, locale=locale, translator=i.client.translator
                )
                return await relic_set_ui.start(i)

            if category is yatta.ItemCategory.CHARACTERS:
                try:
                    character_id = int(query)
                except ValueError as e:
                    raise InvalidQueryError from e

                character_ui = HSRCharacterUI(
                    character_id,
                    author=i.user,
                    locale=locale,
                    translator=i.client.translator,
                )
                return await character_ui.start(i)

    @search_command.autocomplete("category_value")
    async def search_command_category_autocomplete(
        self, i: INTERACTION, current: str
    ) -> list[app_commands.Choice]:
        try:
            game = Game(i.namespace.game)
        except ValueError:
            return [self._get_error_app_command_choice("Invalid game selected")]

        return [
            app_commands.Choice(
                name=app_commands.locale_str(c, warn_no_key=False),
                value=c,
            )
            for c in self._search_categories[game]
            if current.lower() in c.lower()
        ]

    @search_command.autocomplete("query")
    async def search_command_query_autocomplete(
        self, i: INTERACTION, current: str
    ) -> list[app_commands.Choice]:
        try:
            game = Game(i.namespace.game)
        except ValueError:
            return [self._get_error_app_command_choice("Invalid game selected")]

        try:
            if game is Game.GENSHIN:
                category = ambr.ItemCategory(i.namespace.category)
            elif game is Game.STARRAIL:
                category = yatta.ItemCategory(i.namespace.category)
            else:
                return [self._get_error_app_command_choice("Invalid game selected")]
        except ValueError:
            return [self._get_error_app_command_choice("Invalid category selected")]

        if not current:
            locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
            autocomplete_choices = self._search_autocomplete_choices[game][category][locale.value]
        else:
            autocomplete_choices = {
                k: v
                for c in self._search_autocomplete_choices[game][category].values()
                for k, v in c.items()
            }

        choices = [
            app_commands.Choice(name=choice, value=item_id)
            for choice, item_id in autocomplete_choices.items()
            if current.lower() in choice.lower()
        ]

        random.shuffle(choices)
        return choices[:25]


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Hoyo(bot))
