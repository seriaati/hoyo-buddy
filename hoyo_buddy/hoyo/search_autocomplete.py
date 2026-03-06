from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Any, ClassVar

from discord.app_commands import Choice

from hoyo_buddy.constants import LOCALE_TO_AMBR_LANG, LOCALE_TO_YATTA_LANG
from hoyo_buddy.enums import Game
from hoyo_buddy.utils import sleep

from .clients import ambr, yatta

if TYPE_CHECKING:
    from types import CoroutineType

    import aiohttp

    from hoyo_buddy.types import AutocompleteChoices, BetaAutocompleteChoices, ItemCategory, Tasks


class AutocompleteSetup:
    _result: ClassVar[AutocompleteChoices]
    _beta_result: ClassVar[BetaAutocompleteChoices]
    _beta_id_to_category: ClassVar[dict[str, str]]
    """Item ID to ItemCategory.value."""
    _category_beta_ids: ClassVar[dict[tuple[Game, ItemCategory], list[str | int] | list[int]]]
    _tasks: ClassVar[Tasks]

    @classmethod
    def _get_ambr_task(
        cls, api: ambr.AmbrAPIClient, category: ambr.ItemCategory
    ) -> CoroutineType[Any, Any, list[Any]] | None:
        match category:
            case ambr.ItemCategory.CHARACTERS:
                return api.fetch_characters(traveler_gender_symbol=True)
            case ambr.ItemCategory.WEAPONS:
                return api.fetch_weapons()
            case ambr.ItemCategory.ARTIFACT_SETS:
                return api.fetch_artifact_sets()
            case ambr.ItemCategory.FOOD:
                return api.fetch_foods()
            case ambr.ItemCategory.MATERIALS:
                return api.fetch_materials()
            case ambr.ItemCategory.FURNISHINGS:
                return api.fetch_furnitures()
            case ambr.ItemCategory.FURNISHING_SETS:
                return api.fetch_furniture_sets()
            case ambr.ItemCategory.NAMECARDS:
                return api.fetch_namecards()
            case ambr.ItemCategory.LIVING_BEINGS:
                return api.fetch_monsters()
            case ambr.ItemCategory.BOOKS:
                return api.fetch_books()
            case ambr.ItemCategory.TCG:
                return api.fetch_tcg_cards()

    @classmethod
    def _get_yatta_task(
        cls, api: yatta.YattaAPIClient, category: yatta.ItemCategory
    ) -> CoroutineType[Any, Any, list[Any]]:
        match category:
            case yatta.ItemCategory.CHARACTERS:
                return api.fetch_characters(trailblazer_gender_symbol=True)
            case yatta.ItemCategory.LIGHT_CONES:
                return api.fetch_light_cones()
            case yatta.ItemCategory.ITEMS:
                return api.fetch_items()
            case yatta.ItemCategory.RELICS:
                return api.fetch_relic_sets()
            case yatta.ItemCategory.BOOKS:
                return api.fetch_books()

    @classmethod
    async def _setup_ambr(cls, session: aiohttp.ClientSession) -> None:
        game = Game.GENSHIN

        for locale in LOCALE_TO_AMBR_LANG:
            api = ambr.AmbrAPIClient(locale, session=session)
            for category in ambr.ItemCategory:
                coro = cls._get_ambr_task(api, category)
                if coro is not None:
                    task = asyncio.create_task(coro)
                    cls._tasks[game][category][locale] = task
                    await sleep("search_autofill")

    @classmethod
    async def _setup_yatta(cls, session: aiohttp.ClientSession) -> None:
        game = Game.STARRAIL

        for locale in LOCALE_TO_YATTA_LANG:
            api = yatta.YattaAPIClient(locale, session=session)
            for category in yatta.ItemCategory:
                coro = cls._get_yatta_task(api, category)
                task = asyncio.create_task(coro)
                cls._tasks[game][category][locale] = task
                await sleep("search_autofill")

    @classmethod
    async def start(
        cls, session: aiohttp.ClientSession
    ) -> tuple[AutocompleteChoices, dict[str, str], BetaAutocompleteChoices]:
        # Initialize variables
        cls._result = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        cls._beta_result = defaultdict(lambda: defaultdict(list))
        cls._beta_id_to_category = {}
        cls._category_beta_ids = {}
        cls._tasks = defaultdict(lambda: defaultdict(dict))

        creat_task_tasks = [
            asyncio.create_task(cls._setup_ambr(session)),
            asyncio.create_task(cls._setup_yatta(session)),
        ]
        await asyncio.gather(*creat_task_tasks, return_exceptions=True)

        tasks = [
            task
            for categories in cls._tasks.values()
            for locales in categories.values()
            for task in locales.values()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        for game, categories in cls._tasks.items():
            for category, locales in categories.items():
                beta_ids = cls._category_beta_ids.get((game, category), [])
                beta_ids = [str(i) for i in beta_ids]

                for locale, task in locales.items():
                    items = task.result()
                    for item in items:
                        if not hasattr(item, "id") or not hasattr(item, "name"):
                            continue

                        # rarity is None means it's a beta item
                        if hasattr(item, "rarity") and item.rarity is None:
                            continue

                        cls._result[game][category][locale].append(
                            Choice(name=item.name, value=str(item.id))
                        )

        return cls._result, cls._beta_id_to_category, cls._beta_result
