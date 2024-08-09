from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING, Any

import hakushin as hakushin_api
from discord import Locale, app_commands
from discord.ext import commands
from loguru import logger

from hoyo_buddy.constants import locale_to_hakushin_lang

from ..db.models import Settings, get_locale
from ..emojis import PROJECT_AMBER
from ..enums import Game
from ..exceptions import InvalidQueryError
from ..hoyo.clients import ambr, hakushin, yatta
from ..hoyo.search_autocomplete import AutocompleteSetup
from ..l10n import LocaleStr
from ..ui import URLButtonView
from ..ui.hoyo.genshin import search as gi_search
from ..ui.hoyo.genshin.abyss_enemy import AbyssEnemyView
from ..ui.hoyo.hsr import search as hsr_search
from ..ui.hoyo.hsr.search.light_cone import LightConeUI
from ..ui.hoyo.zzz import search as zzz_search
from ..utils import ephemeral

if TYPE_CHECKING:
    from ..bot import HoyoBuddy
    from ..types import Interaction


class Search(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

        self._search_categories: dict[
            Game, list[ambr.ItemCategory | yatta.ItemCategory | hakushin.ZZZItemCategory]
        ] = {
            Game.GENSHIN: list(ambr.ItemCategory),
            Game.STARRAIL: list(yatta.ItemCategory),
            Game.ZZZ: list(hakushin.ZZZItemCategory),
        }
        self._beta_id_to_category: dict[str, str] = {}
        self._tasks: set[asyncio.Task] = set()

    async def cog_load(self) -> None:
        if not self.bot.config.search_autocomplete:
            return

        task = asyncio.create_task(self._setup_search_autocomplete_choices())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _setup_search_autocomplete_choices(self) -> None:
        logger.info("Setting up search autocomplete choices")
        start = self.bot.loop.time()

        try:
            (
                self.bot.autocomplete_choices,
                self._beta_id_to_category,
            ) = await AutocompleteSetup.start(self.bot.translator, self.bot.session)
        except Exception:
            logger.exception("Failed to set up search autocomplete choices")

        logger.info(
            f"Finished setting up search autocomplete choices, took {self.bot.loop.time() - start:.2f} seconds",
        )

    @app_commands.command(
        name=app_commands.locale_str("search"),
        description=app_commands.locale_str(
            "Search anything game related", key="search_command_description"
        ),
    )
    @app_commands.rename(
        game_value=app_commands.locale_str("game", key="search_command_game_param_name"),
        category_value=app_commands.locale_str("category", key="search_cmd_category_param_name"),
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
    async def search_command(  # noqa: C901, PLR0911, PLR0912, PLR0914, PLR0915
        self,
        i: Interaction,
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

        settings = await Settings.get(user_id=i.user.id)
        locale = settings.locale or i.locale

        if query in self._beta_id_to_category:
            if game is Game.GENSHIN:
                try:
                    category = ambr.ItemCategory(category_value)
                except ValueError as e:
                    raise InvalidQueryError from e
            elif game is Game.STARRAIL:
                try:
                    category = yatta.ItemCategory(category_value)
                except ValueError as e:
                    raise InvalidQueryError from e
            else:
                raise InvalidQueryError

            if game is Game.GENSHIN:
                if category is ambr.ItemCategory.UNRELEASED_CONTENT:
                    category = ambr.ItemCategory(self._beta_id_to_category[query])

                match category:
                    case ambr.ItemCategory.CHARACTERS:
                        character_ui = gi_search.CharacterUI(
                            query,
                            author=i.user,
                            locale=locale,
                            translator=i.client.translator,
                            hakushin=True,
                        )
                        await character_ui.update(i)
                    case ambr.ItemCategory.WEAPONS:
                        weapon_ui = gi_search.WeaponUI(
                            query,
                            hakushin=True,
                            author=i.user,
                            locale=locale,
                            translator=i.client.translator,
                        )
                        await weapon_ui.start(i)
                    case ambr.ItemCategory.ARTIFACT_SETS:
                        artifact_set_ui = gi_search.ArtifactSetUI(
                            query,
                            author=i.user,
                            locale=locale,
                            translator=i.client.translator,
                            hakushin=True,
                        )
                        await artifact_set_ui.start(i)
                    case _:
                        raise InvalidQueryError

            elif game is Game.STARRAIL:
                if category is yatta.ItemCategory.UNRELEASED_CONTENT:
                    category = yatta.ItemCategory(self._beta_id_to_category[query])

                match category:
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
                            hakushin=True,
                        )
                        await character_ui.start(i)
                    case yatta.ItemCategory.LIGHT_CONES:
                        light_cone_ui = LightConeUI(
                            query,
                            author=i.user,
                            locale=locale,
                            translator=i.client.translator,
                            hakushin=True,
                        )
                        await light_cone_ui.start(i)
                    case yatta.ItemCategory.RELICS:
                        relic_set_ui = hsr_search.RelicSetUI(
                            query,
                            author=i.user,
                            locale=locale,
                            translator=i.client.translator,
                            hakushin=True,
                        )
                        await relic_set_ui.start(i)
                    case _:
                        raise InvalidQueryError

            return

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
                        hakushin=False,
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
                        await i.response.defer(ephemeral=ephemeral(i))
                        namecard_detail = await api.fetch_namecard_detail(int(query))
                        embed = api.get_namecard_embed(namecard_detail)
                        await i.followup.send(embed=embed)

                case ambr.ItemCategory.ARTIFACT_SETS:
                    artifact_set_ui = gi_search.ArtifactSetUI(
                        query,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                        hakushin=False,
                    )
                    await artifact_set_ui.start(i)

                case ambr.ItemCategory.FOOD:
                    async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                        await i.response.defer(ephemeral=ephemeral(i))
                        food_detail = await api.fetch_food_detail(int(query))
                        embed = api.get_food_embed(food_detail)
                        await i.followup.send(embed=embed)

                case ambr.ItemCategory.MATERIALS:
                    async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                        await i.response.defer(ephemeral=ephemeral(i))
                        material_detail = await api.fetch_material_detail(int(query))
                        embed = api.get_material_embed(material_detail)
                        await i.followup.send(embed=embed)

                case ambr.ItemCategory.FURNISHINGS:
                    async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                        await i.response.defer(ephemeral=ephemeral(i))
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
                        await i.response.defer(ephemeral=ephemeral(i))
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
                        await i.response.defer(ephemeral=ephemeral(i))
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
                        await i.response.defer(ephemeral=ephemeral(i))
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
                        await i.response.defer(ephemeral=ephemeral(i))
                        item = await api.fetch_item_detail(int(query))
                        embed = api.get_item_embed(item)
                        await i.followup.send(embed=embed)

                case yatta.ItemCategory.LIGHT_CONES:
                    light_cone_ui = LightConeUI(
                        query,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                        hakushin=False,
                    )
                    await light_cone_ui.start(i)

                case yatta.ItemCategory.BOOKS:
                    book_ui = hsr_search.BookUI(
                        query, author=i.user, locale=locale, translator=i.client.translator
                    )
                    await book_ui.start(i)

                case yatta.ItemCategory.RELICS:
                    relic_set_ui = hsr_search.RelicSetUI(
                        query,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                        hakushin=False,
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
                        hakushin=False,
                    )
                    await character_ui.start(i)

        elif game is Game.ZZZ:
            try:
                category = hakushin.ZZZItemCategory(category_value)
            except ValueError as e:
                raise InvalidQueryError from e

            match category:
                case hakushin.ZZZItemCategory.AGENTS:
                    try:
                        agent_id = int(query)
                    except ValueError as e:
                        raise InvalidQueryError from e

                    view = zzz_search.AgentSearchView(
                        agent_id,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    await view.start(i)
                case hakushin.ZZZItemCategory.BANGBOOS:
                    try:
                        bangboo_id = int(query)
                    except ValueError as e:
                        raise InvalidQueryError from e

                    await i.response.defer(ephemeral=ephemeral(i))
                    translator = hakushin.HakushinTranslator(locale, i.client.translator)
                    async with hakushin_api.HakushinAPI(
                        hakushin_api.Game.ZZZ, locale_to_hakushin_lang(locale)
                    ) as api:
                        disc = await api.fetch_bangboo_detail(bangboo_id)
                    embed = translator.get_bangboo_embed(disc)
                    await i.followup.send(embed=embed)
                case hakushin.ZZZItemCategory.W_ENGINES:
                    try:
                        engine_id = int(query)
                    except ValueError as e:
                        raise InvalidQueryError from e

                    view = zzz_search.EngineSearchView(
                        engine_id, author=i.user, locale=locale, translator=i.client.translator
                    )
                    await view.start(i)
                case hakushin.ZZZItemCategory.DRIVE_DISCS:
                    try:
                        disc_id = int(query)
                    except ValueError as e:
                        raise InvalidQueryError from e

                    await i.response.defer(ephemeral=ephemeral(i))
                    translator = hakushin.HakushinTranslator(locale, i.client.translator)
                    async with hakushin_api.HakushinAPI(
                        hakushin_api.Game.ZZZ, locale_to_hakushin_lang(locale)
                    ) as api:
                        disc = await api.fetch_drive_disc_detail(disc_id)
                    embed = translator.get_disc_embed(disc)
                    await i.followup.send(embed=embed)

    @search_command.autocomplete("game_value")
    async def search_command_game_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice]:
        locale = await get_locale(i)
        return self.bot.get_enum_autocomplete(
            (Game.GENSHIN, Game.STARRAIL, Game.ZZZ), locale, current
        )

    @search_command.autocomplete("category_value")
    async def search_command_category_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice]:
        locale = await get_locale(i)
        try:
            game = Game(i.namespace.game)
        except ValueError:
            return self.bot.get_error_autocomplete(LocaleStr(key="invalid_game_selected"), locale)

        return self.bot.get_enum_autocomplete(self._search_categories[game], locale, current)

    @search_command.autocomplete("query")
    async def search_command_query_autocomplete(  # noqa: PLR0912, PLR0911
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice]:
        locale = await get_locale(i)
        try:
            game = Game(i.namespace.game)
        except ValueError:
            return self.bot.get_error_autocomplete(LocaleStr(key="invalid_game_selected"), locale)

        try:
            if game is Game.GENSHIN:
                category = ambr.ItemCategory(i.namespace.category)
            elif game is Game.STARRAIL:
                category = yatta.ItemCategory(i.namespace.category)
            elif game is Game.ZZZ:
                category = hakushin.ZZZItemCategory(i.namespace.category)
            else:
                return self.bot.get_error_autocomplete(
                    LocaleStr(key="invalid_game_selected"), locale
                )
        except ValueError:
            return self.bot.get_error_autocomplete(
                LocaleStr(key="invalid_category_selected"), locale
            )

        # Special handling for spiral abyss
        if category is ambr.ItemCategory.SPIRAL_ABYSS:
            return await AbyssEnemyView.get_autocomplete_choices()

        if not self.bot.autocomplete_choices or game not in self.bot.autocomplete_choices:
            return self.bot.get_error_autocomplete(
                LocaleStr(key="search_autocomplete_not_setup"), locale
            )

        try:
            choice_dict = self.bot.autocomplete_choices[game][category][locale.value]
        except KeyError:
            try:
                choice_dict = self.bot.autocomplete_choices[game][category][
                    Locale.american_english.value
                ]
            except KeyError:
                return self.bot.get_error_autocomplete(
                    LocaleStr(key="search_autocomplete_no_results"), locale
                )

        choices = [
            app_commands.Choice(name=choice, value=item_id)
            for choice, item_id in choice_dict.items()
            if current.lower() in choice.lower()
        ]

        if not choices:
            return self.bot.get_error_autocomplete(
                LocaleStr(key="search_autocomplete_no_results"), locale
            )

        random.shuffle(choices)
        return choices[:25]


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Search(bot))
