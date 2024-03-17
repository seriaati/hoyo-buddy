import logging
import random
from typing import TYPE_CHECKING, Any

import discord
from ambr.exceptions import AmbrAPIError
from discord import Locale, app_commands
from discord.ext import commands, tasks
from yatta.exceptions import YattaAPIError

from ..bot.translator import LocaleStr
from ..db.models import Settings
from ..emojis import PROJECT_AMBER
from ..enums import Game
from ..exceptions import InvalidQueryError
from ..hoyo.clients import ambr_client, yatta_client
from ..ui import URLButtonView
from ..ui.hoyo.genshin.search import ArtifactSetUI, BookVolumeUI, CharacterUI, TCGCardUI, WeaponUI
from ..ui.hoyo.hsr.search import BookUI, RelicSetUI
from ..ui.hoyo.hsr.search import CharacterUI as HSRCharacterUI
from ..ui.hoyo.hsr.search.light_cone import LightConeUI

if TYPE_CHECKING:
    from ..bot.bot import INTERACTION, HoyoBuddy

LOGGER_ = logging.getLogger(__name__)


class Search(commands.Cog):
    def __init__(self, bot: "HoyoBuddy") -> None:
        self.bot = bot

        self._search_categories: dict[Game, list[str]] = {
            Game.GENSHIN: [c.value for c in ambr_client.ItemCategory],
            Game.STARRAIL: [c.value for c in yatta_client.ItemCategory],
        }

    async def cog_load(self) -> None:
        self._update_search_autocomplete_choices.start()

    async def cog_unload(self) -> None:
        self._update_search_autocomplete_choices.cancel()

    async def _fetch_item_task(
        self,
        api: ambr_client.AmbrAPIClient | yatta_client.YattaAPIClient,
        item_category: ambr_client.ItemCategory | yatta_client.ItemCategory,
        locale: discord.Locale,
    ) -> None:
        if isinstance(api, ambr_client.AmbrAPIClient) and isinstance(
            item_category, ambr_client.ItemCategory
        ):
            game = Game.GENSHIN
            items = await api.fetch_items(item_category)
        elif isinstance(api, yatta_client.YattaAPIClient) and isinstance(
            item_category, yatta_client.ItemCategory
        ):
            game = Game.STARRAIL
            items = await api.fetch_items_(item_category)
        else:
            msg = f"Invalid item category: {item_category!r}"
            raise TypeError(msg)

        category_locale_choices = (
            self.bot.search_autocomplete_choices.setdefault(game, {})
            .setdefault(item_category, {})
            .setdefault(locale.value, {})
        )
        for item in items:
            category_locale_choices[item.name] = str(item.id)

    async def _setup_search_autocomplete_choices(self) -> None:
        LOGGER_.info("Setting up search autocomplete choices")
        start = self.bot.loop.time()

        for locale in ambr_client.LOCALE_TO_AMBR_LANG:
            async with ambr_client.AmbrAPIClient(locale, self.bot.translator) as api:
                try:
                    await api.fetch_characters()
                except AmbrAPIError as e:
                    LOGGER_.warning(
                        "Ambr API errored with status code %s, ending ambr setup...", e.code
                    )
                    break
                for item_category in ambr_client.ItemCategory:
                    await self._fetch_item_task(api, item_category, locale)

        for locale in yatta_client.LOCALE_TO_YATTA_LANG:
            async with yatta_client.YattaAPIClient(locale, self.bot.translator) as api:
                try:
                    await api.fetch_light_cones()
                except YattaAPIError as e:
                    LOGGER_.warning(
                        "Yatta API errored with status code %s, ending yatta setup...", e.code
                    )
                    break

                for item_category in yatta_client.ItemCategory:
                    await self._fetch_item_task(api, item_category, locale)

        LOGGER_.info(
            "Finished setting up search autocomplete choices, took %.2f seconds",
            self.bot.loop.time() - start,
        )

    @tasks.loop(hours=24)
    async def _update_search_autocomplete_choices(self) -> None:
        if self.bot.env == "dev":
            return
        await self._setup_search_autocomplete_choices()

    @_update_search_autocomplete_choices.before_loop
    async def _before_update_search_autocomplete_choices(self) -> None:
        await self.bot.wait_until_ready()

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
        i: "INTERACTION",
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
                category = ambr_client.ItemCategory(category_value)
            except ValueError as e:
                raise InvalidQueryError from e

            match category:
                case ambr_client.ItemCategory.CHARACTERS:
                    character_ui = CharacterUI(
                        query,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    await character_ui.update(i)

                case ambr_client.ItemCategory.WEAPONS:
                    weapon_ui = WeaponUI(
                        query,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    await weapon_ui.start(i)

                case ambr_client.ItemCategory.NAMECARDS:
                    async with ambr_client.AmbrAPIClient(locale, i.client.translator) as api:
                        await i.response.defer()
                        namecard_detail = await api.fetch_namecard_detail(int(query))
                        embed = api.get_namecard_embed(namecard_detail)
                        await i.followup.send(embed=embed)

                case ambr_client.ItemCategory.ARTIFACT_SETS:
                    artifact_set_ui = ArtifactSetUI(
                        query,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    await artifact_set_ui.start(i)

                case ambr_client.ItemCategory.FOOD:
                    async with ambr_client.AmbrAPIClient(locale, i.client.translator) as api:
                        await i.response.defer()
                        food_detail = await api.fetch_food_detail(int(query))
                        embed = api.get_food_embed(food_detail)
                        await i.followup.send(embed=embed)

                case ambr_client.ItemCategory.MATERIALS:
                    async with ambr_client.AmbrAPIClient(locale, i.client.translator) as api:
                        await i.response.defer()
                        material_detail = await api.fetch_material_detail(int(query))
                        embed = api.get_material_embed(material_detail)
                        await i.followup.send(embed=embed)

                case ambr_client.ItemCategory.FURNISHINGS:
                    async with ambr_client.AmbrAPIClient(locale, i.client.translator) as api:
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

                case ambr_client.ItemCategory.FURNISHING_SETS:
                    async with ambr_client.AmbrAPIClient(locale, i.client.translator) as api:
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

                case ambr_client.ItemCategory.LIVING_BEINGS:
                    async with ambr_client.AmbrAPIClient(locale, i.client.translator) as api:
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

                case ambr_client.ItemCategory.BOOKS:
                    async with ambr_client.AmbrAPIClient(locale, i.client.translator) as api:
                        await i.response.defer()
                        book = await api.fetch_book_detail(int(query))
                        book_volume_ui = BookVolumeUI(
                            book,
                            api.lang.value,
                            author=i.user,
                            locale=locale,
                            translator=i.client.translator,
                        )
                        await book_volume_ui.start(i)

                case ambr_client.ItemCategory.TCG:
                    tcg_card_ui = TCGCardUI(
                        int(query), author=i.user, locale=locale, translator=i.client.translator
                    )
                    await tcg_card_ui.start(i)

        elif game is Game.STARRAIL:
            try:
                category = yatta_client.ItemCategory(category_value)
            except ValueError as e:
                raise InvalidQueryError from e

            match category:
                case yatta_client.ItemCategory.ITEMS:
                    async with yatta_client.YattaAPIClient(locale, i.client.translator) as api:
                        await i.response.defer()
                        item = await api.fetch_item_detail(int(query))
                        embed = api.get_item_embed(item)
                        await i.followup.send(embed=embed)

                case yatta_client.ItemCategory.LIGHT_CONES:
                    light_cone_ui = LightConeUI(
                        query,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    await light_cone_ui.start(i)

                case yatta_client.ItemCategory.BOOKS:
                    book_ui = BookUI(
                        query, author=i.user, locale=locale, translator=i.client.translator
                    )
                    await book_ui.start(i)

                case yatta_client.ItemCategory.RELICS:
                    relic_set_ui = RelicSetUI(
                        query, author=i.user, locale=locale, translator=i.client.translator
                    )
                    await relic_set_ui.start(i)

                case yatta_client.ItemCategory.CHARACTERS:
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
                    await character_ui.start(i)

    @search_command.autocomplete("category_value")
    async def search_command_category_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice]:
        try:
            game = Game(i.namespace.game)
        except ValueError:
            return [
                self.bot.get_error_app_command_choice(
                    LocaleStr("Invalid game selected", key="invalid_category_selected")
                )
            ]

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
        self, i: "INTERACTION", current: str
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
                category = ambr_client.ItemCategory(i.namespace.category)
            elif game is Game.STARRAIL:
                category = yatta_client.ItemCategory(i.namespace.category)
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


async def setup(bot: "HoyoBuddy") -> None:
    await bot.add_cog(Search(bot))
