from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any

import hakushin
from discord import Locale, app_commands
from discord.ext import commands

from ..bot.translator import LocaleStr
from ..db.models import Settings
from ..emojis import PROJECT_AMBER
from ..enums import Game
from ..exceptions import InvalidQueryError
from ..hoyo.clients import ambr, yatta
from ..hoyo.search_autocomplete import AutocompleteSetup
from ..ui import URLButtonView
from ..ui.hoyo.genshin import search as gi_search
from ..ui.hoyo.genshin.abyss_enemy import AbyssEnemyView
from ..ui.hoyo.genshin.search import hakushin as gi_hakushin_search
from ..ui.hoyo.hsr import search as hsr_search
from ..ui.hoyo.hsr.search.light_cone import LightConeUI

if TYPE_CHECKING:
    from ..bot.bot import INTERACTION, HoyoBuddy

LOGGER_ = logging.getLogger(__name__)


class Search(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

        self._search_categories: dict[Game, list[str]] = {
            Game.GENSHIN: [c.value for c in ambr.ItemCategory],
            Game.STARRAIL: [c.value for c in yatta.ItemCategory],
        }
        self._beta_ids: set[int] = set()
        self._tasks: set[asyncio.Task] = set()

    async def cog_load(self) -> None:
        # if self.bot.env == "dev":
        #     return

        task = asyncio.create_task(self._setup_search_autocomplete_choices())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _setup_search_autocomplete_choices(self) -> None:
        LOGGER_.info("Setting up search autocomplete choices")
        start = self.bot.loop.time()

        try:
            self.bot.search_autocomplete_choices = await AutocompleteSetup.start(
                self.bot.translator, self.bot.session
            )
        except Exception:
            LOGGER_.exception("Failed to set up search autocomplete choices")

        async with hakushin.HakushinAPI() as api:
            gi_new = await api.fetch_new(hakushin.Game.GI)
            hsr_new = await api.fetch_new(hakushin.Game.HSR)

        self._beta_ids = set(
            gi_new.artifact_set_ids
            + gi_new.character_ids
            + gi_new.weapon_ids
            + hsr_new.character_ids
            + hsr_new.light_cone_ids
            + hsr_new.relic_set_ids
        )

        LOGGER_.info(
            "Finished setting up search autocomplete choices, took %.2f seconds",
            self.bot.loop.time() - start,
        )

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

        if int(query) in self._beta_ids:
            try:
                category = ambr.ItemCategory(category_value)
            except ValueError as e:
                try:
                    category = yatta.ItemCategory(category_value)
                except ValueError:
                    raise InvalidQueryError from e

            match category:
                case ambr.ItemCategory.CHARACTERS:
                    character_ui = gi_hakushin_search.CharacterUI(
                        query,
                        author=i.user,
                        locale=i.locale,
                        translator=i.client.translator,
                    )
                    await character_ui.update(i)
                case ambr.ItemCategory.WEAPONS:
                    weapon_ui = gi_search.WeaponUI(
                        query,
                        hakushin=True,
                        author=i.user,
                        locale=i.locale,
                        translator=i.client.translator,
                    )
                    await weapon_ui.start(i)

            return

        try:
            game = Game(game_value)
        except ValueError as e:
            raise InvalidQueryError from e

        settings = await Settings.get(user_id=i.user.id)
        locale = settings.locale or i.locale

        if game is Game.GENSHIN:
            try:
                category = ambr.ItemCategory(category_value)
            except ValueError as e:
                raise InvalidQueryError from e

            match category:
                case ambr.ItemCategory.CHARACTERS:
                    character_ui = gi_search.CharacterUI(
                        query,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    await character_ui.update(i)

                case ambr.ItemCategory.WEAPONS:
                    weapon_ui = gi_search.WeaponUI(
                        query,
                        hakushin=False,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    await weapon_ui.start(i)

                case ambr.ItemCategory.NAMECARDS:
                    async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                        await i.response.defer()
                        namecard_detail = await api.fetch_namecard_detail(int(query))
                        embed = api.get_namecard_embed(namecard_detail)
                        await i.followup.send(embed=embed)

                case ambr.ItemCategory.ARTIFACT_SETS:
                    artifact_set_ui = gi_search.ArtifactSetUI(
                        query,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    await artifact_set_ui.start(i)

                case ambr.ItemCategory.FOOD:
                    async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                        await i.response.defer()
                        food_detail = await api.fetch_food_detail(int(query))
                        embed = api.get_food_embed(food_detail)
                        await i.followup.send(embed=embed)

                case ambr.ItemCategory.MATERIALS:
                    async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                        await i.response.defer()
                        material_detail = await api.fetch_material_detail(int(query))
                        embed = api.get_material_embed(material_detail)
                        await i.followup.send(embed=embed)

                case ambr.ItemCategory.FURNISHINGS:
                    async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                        await i.response.defer()
                        furniture_detail = await api.fetch_furniture_detail(int(query))
                        embed = api.get_furniture_embed(furniture_detail)
                        await i.followup.send(
                            embed=embed,
                            view=URLButtonView(
                                i.client.translator,
                                locale,
                                url=f"https://ambr.top/{api.lang.value}/archive/furniture/{query}/",
                                label="ambr.top",
                                emoji=PROJECT_AMBER,
                            ),
                        )

                case ambr.ItemCategory.FURNISHING_SETS:
                    async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                        await i.response.defer()
                        furniture_set_detail = await api.fetch_furniture_set_detail(int(query))
                        embed = api.get_furniture_set_embed(furniture_set_detail)
                        await i.followup.send(
                            embed=embed,
                            view=URLButtonView(
                                i.client.translator,
                                locale,
                                url=f"https://ambr.top/{api.lang.value}/archive/furnitureSuite/{query}/",
                                label="ambr.top",
                                emoji=PROJECT_AMBER,
                            ),
                        )

                case ambr.ItemCategory.LIVING_BEINGS:
                    async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                        await i.response.defer()
                        monster_detail = await api.fetch_monster_detail(int(query))
                        embed = api.get_monster_embed(monster_detail)
                        await i.followup.send(
                            embed=embed,
                            view=URLButtonView(
                                i.client.translator,
                                locale,
                                url=f"https://ambr.top/{api.lang.value}/archive/monster/{query}/",
                                label="ambr.top",
                                emoji=PROJECT_AMBER,
                            ),
                        )

                case ambr.ItemCategory.BOOKS:
                    async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                        await i.response.defer()
                        book = await api.fetch_book_detail(int(query))
                        book_volume_ui = gi_search.BookVolumeUI(
                            book,
                            api.lang.value,
                            author=i.user,
                            locale=locale,
                            translator=i.client.translator,
                        )
                        await book_volume_ui.start(i)

                case ambr.ItemCategory.TCG:
                    tcg_card_ui = gi_search.TCGCardUI(
                        int(query), author=i.user, locale=locale, translator=i.client.translator
                    )
                    await tcg_card_ui.start(i)

                case ambr.ItemCategory.SPIRAL_ABYSS:
                    try:
                        index = int(query)
                    except ValueError as e:
                        raise InvalidQueryError from e

                    view = AbyssEnemyView(
                        settings.dark_mode,
                        index,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    await view.start(i)

        elif game is Game.STARRAIL:
            try:
                category = yatta.ItemCategory(category_value)
            except ValueError as e:
                raise InvalidQueryError from e

            match category:
                case yatta.ItemCategory.ITEMS:
                    async with yatta.YattaAPIClient(locale, i.client.translator) as api:
                        await i.response.defer()
                        item = await api.fetch_item_detail(int(query))
                        embed = api.get_item_embed(item)
                        await i.followup.send(embed=embed)

                case yatta.ItemCategory.LIGHT_CONES:
                    light_cone_ui = LightConeUI(
                        query,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    await light_cone_ui.start(i)

                case yatta.ItemCategory.BOOKS:
                    book_ui = hsr_search.BookUI(
                        query, author=i.user, locale=locale, translator=i.client.translator
                    )
                    await book_ui.start(i)

                case yatta.ItemCategory.RELICS:
                    relic_set_ui = hsr_search.RelicSetUI(
                        query, author=i.user, locale=locale, translator=i.client.translator
                    )
                    await relic_set_ui.start(i)

                case yatta.ItemCategory.CHARACTERS:
                    try:
                        character_id = int(query)
                    except ValueError as e:
                        raise InvalidQueryError from e

                    character_ui = hsr_search.CharacterUI(
                        character_id,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    await character_ui.start(i)

    @search_command.autocomplete("category_value")
    async def search_command_category_autocomplete(
        self, i: INTERACTION, current: str
    ) -> list[app_commands.Choice]:
        try:
            game = Game(i.namespace.game)
        except ValueError:
            return [
                self.bot.get_error_app_command_choice(
                    LocaleStr("Invalid game selected", key="invalid_category_selected")
                )
            ]

        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        return [
            app_commands.Choice(
                name=LocaleStr(c, warn_no_key=False).translate(i.client.translator, locale),
                value=c,
            )
            for c in self._search_categories[game]
            if current.lower() in c.lower()
        ]

    @search_command.autocomplete("query")
    async def search_command_query_autocomplete(  # noqa: PLR0912
        self, i: INTERACTION, current: str
    ) -> list[app_commands.Choice]:
        try:
            game = Game(i.namespace.game)
        except ValueError:
            return [
                self.bot.get_error_app_command_choice(
                    LocaleStr("Invalid game selected", key="invalid_game_selected")
                )
            ]

        try:
            if game is Game.GENSHIN:
                category = ambr.ItemCategory(i.namespace.category)
            elif game is Game.STARRAIL:
                category = yatta.ItemCategory(i.namespace.category)
            else:
                return [
                    self.bot.get_error_app_command_choice(
                        LocaleStr("Invalid game selected", key="invalid_game_selected")
                    )
                ]
        except ValueError:
            return [
                self.bot.get_error_app_command_choice(
                    LocaleStr("Invalid category selected", key="invalid_category_selected")
                )
            ]

        # Special handling for spiral abyss
        if category is ambr.ItemCategory.SPIRAL_ABYSS:
            return await AbyssEnemyView.get_autocomplete_choices()

        if (
            not self.bot.search_autocomplete_choices
            or game not in self.bot.search_autocomplete_choices
        ):
            return [
                self.bot.get_error_app_command_choice(
                    LocaleStr(
                        "Search autocomplete choices not set up yet, please try again later.",
                        key="search_autocomplete_not_setup",
                    )
                )
            ]

        if not current:
            locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
            try:
                choice_dict = self.bot.search_autocomplete_choices[game][category][locale.value]
            except KeyError:
                choice_dict = self.bot.search_autocomplete_choices[game][category][
                    Locale.american_english.value
                ]
        else:
            choice_dict = {
                k: v
                for c in self.bot.search_autocomplete_choices[game][category].values()
                for k, v in c.items()
            }

        choices = [
            app_commands.Choice(name=choice, value=item_id)
            for choice, item_id in choice_dict.items()
            if current.lower() in choice.lower()
        ]

        random.shuffle(choices)
        return choices[:25]


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Search(bot))
